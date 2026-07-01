import uuid

import pytest


class TestReconciliationEngine:
    def test_amount_match_within_tolerance(self):
        from decimal import Decimal
        from app.services.reconciliation_service import ReconciliationService
        from app.models.reconciliation import ReconciliationStatus

        class MockDB:
            pass

        svc = ReconciliationService.__new__(ReconciliationService)
        svc._tolerance = Decimal("0.01")

        from app.models.invoice import Invoice

        invoice = Invoice()
        invoice.total_amount = Decimal("1005.00")

        status, disc_type, diff, confidence = svc._match_amount(invoice, Decimal("1000.00"))
        # 1% of 1000 = 10, diff = 5 → within tolerance
        assert status == ReconciliationStatus.MATCHED
        assert disc_type is None
        assert confidence > 0.99

    def test_amount_mismatch_outside_tolerance(self):
        from decimal import Decimal
        from app.services.reconciliation_service import ReconciliationService
        from app.models.reconciliation import ReconciliationStatus, DiscrepancyType

        svc = ReconciliationService.__new__(ReconciliationService)
        svc._tolerance = Decimal("0.01")

        from app.models.invoice import Invoice

        invoice = Invoice()
        invoice.total_amount = Decimal("1200.00")

        status, disc_type, diff, confidence = svc._match_amount(invoice, Decimal("1000.00"))
        assert status == ReconciliationStatus.DISCREPANCY
        assert disc_type == DiscrepancyType.AMOUNT_MISMATCH
        assert diff == Decimal("200.00")

    def test_missing_expected_amount(self):
        from decimal import Decimal
        from app.services.reconciliation_service import ReconciliationService
        from app.models.reconciliation import ReconciliationStatus

        svc = ReconciliationService.__new__(ReconciliationService)
        svc._tolerance = Decimal("0.01")

        from app.models.invoice import Invoice

        invoice = Invoice()
        invoice.total_amount = Decimal("500.00")

        status, disc_type, diff, confidence = svc._match_amount(invoice, None)
        assert status == ReconciliationStatus.PARTIAL_MATCH


class TestSelfConsistencyReconciliation:
    """With no external reference amount (the automated pipeline), reconcile
    falls back to checking the invoice's own arithmetic so a clean invoice can
    actually reach RECONCILED instead of being stuck at VALIDATED forever."""

    def _make(self, db, admin_user, **fields):
        from decimal import Decimal
        from app.models.invoice import Invoice, InvoiceStatus

        inv = Invoice(
            id=uuid.uuid4(), original_filename="c.pdf", storage_path="c",
            content_type="application/pdf", uploaded_by=admin_user.id,
            tenant_id=admin_user.tenant_id, status=InvoiceStatus.EXTRACTED,
            **{k: Decimal(v) if isinstance(v, str) else v for k, v in fields.items()},
        )
        db.add(inv)
        db.commit()
        return inv

    def test_internally_consistent_invoice_reconciles(self, db, admin_user):
        from app.models.invoice import Invoice, InvoiceStatus
        from app.models.reconciliation import ReconciliationRecord, ReconciliationStatus
        from app.schemas.reconciliation import ReconciliationRequest
        from app.services.reconciliation_service import ReconciliationService

        inv = self._make(db, admin_user, subtotal="1000.00", total_tax="180.00",
                        total_amount="1180.00")

        ReconciliationService(db).reconcile(
            ReconciliationRequest(invoice_id=inv.id, reference_document_type="workflow"),
            admin_user,
        )

        reloaded = db.query(Invoice).filter(Invoice.id == inv.id).one()
        assert reloaded.status == InvoiceStatus.RECONCILED
        rec = db.query(ReconciliationRecord).filter(
            ReconciliationRecord.invoice_id == inv.id
        ).one()
        assert rec.status == ReconciliationStatus.MATCHED

    def test_reconcile_is_idempotent_no_duplicate_record(self, db, admin_user):
        """A workflow retry / duplicate job must not create a second record for
        an already-reconciled invoice (Priority 7: duplicate execution)."""
        from app.models.reconciliation import ReconciliationRecord
        from app.schemas.reconciliation import ReconciliationRequest
        from app.services.reconciliation_service import ReconciliationService

        inv = self._make(db, admin_user, subtotal="1000.00", total_tax="0.00",
                        total_amount="1000.00")
        svc = ReconciliationService(db)
        req = ReconciliationRequest(invoice_id=inv.id, reference_document_type="workflow")

        first = svc.reconcile(req, admin_user)
        second = svc.reconcile(req, admin_user)  # replay

        assert first.id == second.id
        assert db.query(ReconciliationRecord).filter(
            ReconciliationRecord.invoice_id == inv.id
        ).count() == 1

    def test_internally_inconsistent_invoice_is_held(self, db, admin_user):
        from app.models.invoice import Invoice, InvoiceStatus
        from app.schemas.reconciliation import ReconciliationRequest
        from app.services.reconciliation_service import ReconciliationService

        # subtotal + tax = 1180, but the stated total is 2000 -- the invoice
        # doesn't add up, so it must be held for review, not reconciled.
        inv = self._make(db, admin_user, subtotal="1000.00", total_tax="180.00",
                        total_amount="2000.00")

        ReconciliationService(db).reconcile(
            ReconciliationRequest(invoice_id=inv.id, reference_document_type="workflow"),
            admin_user,
        )

        reloaded = db.query(Invoice).filter(Invoice.id == inv.id).one()
        assert reloaded.status == InvoiceStatus.VALIDATED


class TestReconciliationAPI:
    def test_list_records_unauthenticated(self, client):
        resp = client.get("/api/v1/reconciliation")
        assert resp.status_code == 401

    def test_reconcile_nonexistent_invoice(self, client, admin_user, auth_headers):
        resp = client.post(
            "/api/v1/reconciliation",
            json={"invoice_id": str(uuid.uuid4())},
            headers=auth_headers,
        )
        assert resp.status_code == 400
