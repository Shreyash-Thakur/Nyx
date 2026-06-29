from __future__ import annotations

import uuid
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.orm import Session

from app.config import settings
from app.core.events import DomainEvent, event_bus
from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models.audit_log import AuditEventType
from app.models.invoice import Invoice, InvoiceStatus
from app.models.reconciliation import (
    DiscrepancyType,
    ReconciliationRecord,
    ReconciliationStatus,
)
from app.models.user import User
from app.repositories.audit_repository import AuditRepository
from app.repositories.invoice_repository import InvoiceRepository
from app.repositories.reconciliation_repository import ReconciliationRepository
from app.schemas.reconciliation import ReconciliationFilter, ReconciliationRequest, ReconciliationResolveRequest

logger = get_logger(__name__)


class ReconciliationService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.invoice_repo = InvoiceRepository(db)
        self.recon_repo = ReconciliationRepository(db)
        self.audit_repo = AuditRepository(db)
        self._tolerance = Decimal(str(settings.RECONCILIATION_TOLERANCE_PERCENT))

    def reconcile(self, payload: ReconciliationRequest, current_user: User) -> ReconciliationRecord:
        invoice = self.invoice_repo.get(payload.invoice_id)
        if not invoice:
            raise NotFoundError("Invoice", str(payload.invoice_id))

        if invoice.status not in (InvoiceStatus.EXTRACTED, InvoiceStatus.VALIDATED, InvoiceStatus.RECONCILED):
            raise ValidationError(
                f"Invoice must be extracted before reconciliation (current status: {invoice.status})"
            )

        # Duplicate check
        duplicate = self._check_duplicate(invoice)
        if duplicate:
            rec = self._create_record(
                invoice=invoice,
                status=ReconciliationStatus.DUPLICATE,
                discrepancy_type=DiscrepancyType.DUPLICATE_INVOICE,
                confidence_score=1.0,
                notes=f"Duplicate of invoice {duplicate.id}",
                matched_by=current_user.id,
            )
            invoice.status = InvoiceStatus.DUPLICATE
            self.audit_repo.log(
                AuditEventType.INVOICE_DUPLICATE_DETECTED,
                f"Duplicate invoice detected: {invoice.id}",
                user_id=current_user.id,
                invoice_id=invoice.id,
            )
            self.db.commit()
            return rec

        # Amount matching
        status, discrepancy_type, discrepancy_amount, confidence = self._match_amount(
            invoice, payload.expected_amount
        )

        rec = self._create_record(
            invoice=invoice,
            status=status,
            discrepancy_type=discrepancy_type,
            confidence_score=confidence,
            reference_document_id=payload.reference_document_id,
            reference_document_type=payload.reference_document_type,
            expected_amount=payload.expected_amount,
            actual_amount=invoice.total_amount,
            discrepancy_amount=discrepancy_amount,
            tolerance_applied=self._tolerance * (payload.expected_amount or Decimal("0")),
            notes=payload.notes,
            matched_by=current_user.id,
        )

        if status == ReconciliationStatus.MATCHED:
            invoice.status = InvoiceStatus.RECONCILED
        else:
            invoice.status = InvoiceStatus.VALIDATED  # Hold for review

        self.audit_repo.log(
            AuditEventType.RECONCILIATION_STARTED,
            f"Reconciliation {status.value} for invoice {invoice.id}",
            user_id=current_user.id,
            invoice_id=invoice.id,
            extra_data={
                "status": status.value,
                "confidence": confidence,
                "discrepancy": str(discrepancy_amount) if discrepancy_amount else None,
            },
        )
        event_bus.publish(
            self.db,
            DomainEvent(
                name="reconciliation.completed",
                aggregate_type="invoice",
                aggregate_id=invoice.id,
                actor_id=current_user.id,
                tenant_id=invoice.tenant_id,
                payload={"status": status.value, "confidence": confidence},
            ),
        )
        self.db.commit()
        return rec

    def resolve(
        self,
        record_id: uuid.UUID,
        payload: ReconciliationResolveRequest,
        current_user: User,
    ) -> ReconciliationRecord:
        record = self.recon_repo.get_or_raise(record_id)
        record.status = payload.status
        record.resolution_notes = payload.resolution_notes
        record.matched_by = current_user.id
        self.recon_repo.save(record)

        if payload.status == ReconciliationStatus.MATCHED:
            invoice = self.invoice_repo.get(record.invoice_id)
            if invoice:
                invoice.status = InvoiceStatus.RECONCILED

        self.audit_repo.log(
            AuditEventType.RECONCILIATION_RESOLVED,
            f"Reconciliation record {record_id} resolved as {payload.status}",
            user_id=current_user.id,
            invoice_id=record.invoice_id,
            extra_data={"resolution_notes": payload.resolution_notes},
        )
        self.db.commit()
        return record

    def list(
        self,
        filters: ReconciliationFilter,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ReconciliationRecord], int]:
        offset = (page - 1) * page_size
        return self.recon_repo.filter_paginated(filters, limit=page_size, offset=offset)

    def get_for_invoice(self, invoice_id: uuid.UUID) -> list[ReconciliationRecord]:
        return self.recon_repo.get_by_invoice(invoice_id)

    # ── Private helpers ────────────────────────────────────────────────────

    def _check_duplicate(self, invoice: Invoice) -> Invoice | None:
        if not all([invoice.invoice_number, invoice.vendor_id, invoice.invoice_date]):
            return None
        duplicates = self.invoice_repo.find_duplicates(
            invoice.invoice_number,
            invoice.vendor_id,
            invoice.invoice_date,
            window_days=settings.RECONCILIATION_DUPLICATE_WINDOW_DAYS,
        )
        others = [d for d in duplicates if d.id != invoice.id]
        return others[0] if others else None

    def _match_amount(
        self,
        invoice: Invoice,
        expected_amount: Decimal | None,
    ) -> tuple[ReconciliationStatus, DiscrepancyType | None, Decimal | None, float]:
        if expected_amount is None or invoice.total_amount is None:
            return ReconciliationStatus.PARTIAL_MATCH, None, None, 0.5

        actual = invoice.total_amount
        expected = expected_amount
        diff = abs(actual - expected)
        tolerance = (expected * self._tolerance).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        if diff <= tolerance:
            confidence = float(1 - (diff / expected if expected else 0))
            return ReconciliationStatus.MATCHED, None, diff, round(confidence, 4)

        confidence = max(0.0, float(1 - (diff / expected)))
        return (
            ReconciliationStatus.DISCREPANCY,
            DiscrepancyType.AMOUNT_MISMATCH,
            diff,
            round(confidence, 4),
        )

    def _create_record(self, invoice: Invoice, **kwargs) -> ReconciliationRecord:
        record = ReconciliationRecord(
            invoice_id=invoice.id, tenant_id=invoice.tenant_id, **kwargs
        )
        return self.recon_repo.save(record)
