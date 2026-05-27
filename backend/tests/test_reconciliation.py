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
