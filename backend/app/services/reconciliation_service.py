from __future__ import annotations

import uuid
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.orm import Session

from app.config import settings
from app.core.events import DomainEvent, event_bus
from app.core.exceptions import ValidationError
from app.core.logging import get_logger
from app.models.invoice import Invoice, InvoiceStatus
from app.models.reconciliation import (
    DiscrepancyType,
    ReconciliationRecord,
    ReconciliationStatus,
)
from app.models.user import User
from app.repositories.invoice_repository import InvoiceRepository
from app.repositories.reconciliation_repository import ReconciliationRepository
from app.schemas.reconciliation import ReconciliationFilter, ReconciliationRequest, ReconciliationResolveRequest

logger = get_logger(__name__)


class ReconciliationService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.invoice_repo = InvoiceRepository(db)
        self.recon_repo = ReconciliationRepository(db)
        self._tolerance = Decimal(str(settings.RECONCILIATION_TOLERANCE_PERCENT))

    def reconcile(self, payload: ReconciliationRequest, current_user: User) -> ReconciliationRecord:
        invoice = self.invoice_repo.get_for_tenant_or_raise(
            payload.invoice_id, current_user.tenant_id
        )

        if invoice.status not in (
            InvoiceStatus.EXTRACTED, InvoiceStatus.VALIDATED,
            InvoiceStatus.APPROVED, InvoiceStatus.RECONCILED,
        ):
            raise ValidationError(
                f"Invoice must be extracted before reconciliation (current status: {invoice.status})"
            )

        # Idempotency: a workflow retry / duplicate job must not create a second
        # reconciliation record for an invoice that is already reconciled. Return
        # the existing matched record instead of matching (and recording) again.
        if invoice.status == InvoiceStatus.RECONCILED:
            existing = [
                r for r in self.recon_repo.get_by_invoice(invoice.id, invoice.tenant_id)
                if r.status == ReconciliationStatus.MATCHED
            ]
            if existing:
                logger.info("reconcile_skipped_already_reconciled", invoice_id=str(invoice.id))
                return existing[0]

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
            event_bus.publish(
                self.db,
                DomainEvent(
                    name="invoice.duplicate_detected",
                    aggregate_type="invoice",
                    aggregate_id=invoice.id,
                    actor_id=current_user.id,
                    tenant_id=invoice.tenant_id,
                    payload={
                        "description": f"Duplicate invoice detected: {invoice.id}",
                        "duplicate_of": str(duplicate.id),
                    },
                ),
            )
            self.db.commit()
            return rec

        # Amount matching. When no external expected amount is supplied (the
        # automated pipeline has no PO/GRN to match against), fall back to a
        # self-consistency check against the invoice's own declared arithmetic
        # (subtotal + taxes). Without this, an automatically-reconciled invoice
        # could never reach MATCHED/RECONCILED -- it would sit at VALIDATED
        # forever, one step short of the accounting export.
        expected_amount = payload.expected_amount
        reference_type = payload.reference_document_type
        if expected_amount is None:
            expected_amount = self._derive_expected_amount(invoice)
            if expected_amount is not None:
                reference_type = reference_type or "self_consistency"

        status, discrepancy_type, discrepancy_amount, confidence = self._match_amount(
            invoice, expected_amount
        )

        rec = self._create_record(
            invoice=invoice,
            status=status,
            discrepancy_type=discrepancy_type,
            confidence_score=confidence,
            reference_document_id=payload.reference_document_id,
            reference_document_type=reference_type,
            expected_amount=expected_amount,
            actual_amount=invoice.total_amount,
            discrepancy_amount=discrepancy_amount,
            tolerance_applied=self._tolerance * (expected_amount or Decimal("0")),
            notes=payload.notes,
            matched_by=current_user.id,
        )

        if status == ReconciliationStatus.MATCHED:
            invoice.status = InvoiceStatus.RECONCILED
        else:
            invoice.status = InvoiceStatus.VALIDATED  # Hold for review

        event_bus.publish(
            self.db,
            DomainEvent(
                name="reconciliation.completed",
                aggregate_type="invoice",
                aggregate_id=invoice.id,
                actor_id=current_user.id,
                tenant_id=invoice.tenant_id,
                payload={
                    "description": f"Reconciliation {status.value} for invoice {invoice.id}",
                    "status": status.value,
                    "confidence": confidence,
                    "discrepancy": str(discrepancy_amount) if discrepancy_amount else None,
                },
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
        record = self.recon_repo.get_for_tenant_or_raise(record_id, current_user.tenant_id)
        record.status = payload.status
        record.resolution_notes = payload.resolution_notes
        record.matched_by = current_user.id
        self.recon_repo.save(record)

        if payload.status == ReconciliationStatus.MATCHED:
            invoice = self.invoice_repo.get_for_tenant(record.invoice_id, current_user.tenant_id)
            if invoice:
                invoice.status = InvoiceStatus.RECONCILED

        event_bus.publish(
            self.db,
            DomainEvent(
                name="reconciliation.resolved",
                aggregate_type="invoice",
                aggregate_id=record.invoice_id,
                actor_id=current_user.id,
                tenant_id=record.tenant_id,
                payload={
                    "description": f"Reconciliation record {record_id} resolved as {payload.status}",
                    "resolution_notes": payload.resolution_notes,
                },
            ),
        )
        self.db.commit()
        return record

    def list(
        self,
        filters: ReconciliationFilter,
        tenant_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ReconciliationRecord], int]:
        offset = (page - 1) * page_size
        return self.recon_repo.filter_paginated(
            filters, tenant_id=tenant_id, limit=page_size, offset=offset
        )

    def get_for_invoice(
        self, invoice_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> list[ReconciliationRecord]:
        return self.recon_repo.get_by_invoice(invoice_id, tenant_id)

    # ── Private helpers ────────────────────────────────────────────────────

    def _check_duplicate(self, invoice: Invoice) -> Invoice | None:
        if not all([invoice.invoice_number, invoice.vendor_id, invoice.invoice_date]):
            return None
        duplicates = self.invoice_repo.find_duplicates(
            invoice.invoice_number,
            invoice.vendor_id,
            invoice.invoice_date,
            invoice.tenant_id,
            window_days=settings.RECONCILIATION_DUPLICATE_WINDOW_DAYS,
        )
        others = [d for d in duplicates if d.id != invoice.id]
        return others[0] if others else None

    def _derive_expected_amount(self, invoice: Invoice) -> Decimal | None:
        """A self-consistency 'expected' total from the invoice's own fields:
        ``subtotal + taxes``. Used only when no external reference amount is
        supplied. Returns None when there is no declared subtotal to build on
        (nothing to check the total against) -- preserving the existing
        'held for review' outcome for a bare total with no breakdown.
        """
        if invoice.subtotal is None:
            return None
        tax = invoice.total_tax
        if tax is None:
            tax = sum(
                (amt for amt in (invoice.cgst_amount, invoice.sgst_amount, invoice.igst_amount)
                 if amt is not None),
                Decimal("0"),
            )
        return invoice.subtotal + tax

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
