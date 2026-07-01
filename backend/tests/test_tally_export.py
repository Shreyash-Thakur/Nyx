"""Tally XML export -- dry-run only (Priority 5 highest-value ERP capability)."""
import uuid
from datetime import date
from decimal import Decimal

import pytest

from app.models.invoice import Invoice, InvoiceStatus
from app.models.vendor import Vendor


def _make_reconciled_invoice(db, admin_user):
    vendor = Vendor(name="Acme Trading Co", normalized_name="acme trading co", tenant_id=admin_user.tenant_id)
    db.add(vendor)
    db.flush()
    inv = Invoice(
        id=uuid.uuid4(), original_filename="f.pdf", storage_path="s",
        content_type="application/pdf", uploaded_by=admin_user.id,
        tenant_id=admin_user.tenant_id, status=InvoiceStatus.RECONCILED,
        invoice_number="INV-42", invoice_date=date(2026, 6, 15), vendor_id=vendor.id,
        subtotal=Decimal("1000.00"), cgst_amount=Decimal("90.00"), sgst_amount=Decimal("90.00"),
        total_tax=Decimal("180.00"), total_amount=Decimal("1180.00"),
    )
    db.add(inv)
    db.commit()
    return inv


def test_build_tally_xml_is_deterministic(db, admin_user):
    from app.services.tally_export_service import build_tally_xml

    inv = _make_reconciled_invoice(db, admin_user)
    narration1, xml1 = build_tally_xml(inv)
    narration2, xml2 = build_tally_xml(inv)

    assert xml1 == xml2  # pure function: same invoice -> byte-identical XML
    assert "Acme Trading Co" in narration1
    assert "INV-42" in narration1
    assert "<VOUCHER" in xml1
    assert "1180.00" in xml1  # vendor credit for the full total
    assert "CGST" in xml1 and "90.00" in xml1


def test_dry_run_endpoint_returns_xml_for_reconciled_invoice(client, db, admin_user, auth_headers):
    inv = _make_reconciled_invoice(db, admin_user)

    resp = client.get(f"/api/v1/invoices/{inv.id}/tally-export", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["voucher_type"] == "Purchase"
    assert "<ENVELOPE>" in body["xml"]


def test_dry_run_rejects_unreconciled_invoice(client, db, admin_user, auth_headers):
    inv = _make_reconciled_invoice(db, admin_user)
    inv.status = InvoiceStatus.EXTRACTED
    db.commit()

    resp = client.get(f"/api/v1/invoices/{inv.id}/tally-export", headers=auth_headers)
    assert resp.status_code == 400


def test_dry_run_is_tenant_scoped(client, db, admin_user, auth_headers):
    other_tenant_invoice = Invoice(
        id=uuid.uuid4(), original_filename="f.pdf", storage_path="s",
        content_type="application/pdf", uploaded_by=admin_user.id,
        tenant_id=uuid.uuid4(), status=InvoiceStatus.RECONCILED,
        total_amount=Decimal("100.00"),
    )
    db.add(other_tenant_invoice)
    db.commit()

    resp = client.get(
        f"/api/v1/invoices/{other_tenant_invoice.id}/tally-export", headers=auth_headers
    )
    assert resp.status_code == 404


def test_dry_run_produces_an_audit_row(client, db, admin_user, auth_headers):
    from app.models.audit_log import AuditEventType, AuditLog

    inv = _make_reconciled_invoice(db, admin_user)
    client.get(f"/api/v1/invoices/{inv.id}/tally-export", headers=auth_headers)

    row = (
        db.query(AuditLog)
        .filter(AuditLog.event_type == AuditEventType.INVOICE_TALLY_EXPORT_GENERATED)
        .first()
    )
    assert row is not None
