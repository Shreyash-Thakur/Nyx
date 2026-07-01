"""Human-verify OCR queue (TD-3, Priority 5: verification queues).

A low-confidence OCR read must stop at needs_verification instead of
auto-reconciling a possibly-wrong extraction; a human verify resumes the same
workflow. The confidence gate runs before the approval gate, so a verified
high-value invoice then flows on to the approval gate.
"""
import uuid
from decimal import Decimal

from app.models.invoice import Invoice, InvoiceStatus
from app.models.notification import Notification
from app.models.reconciliation import ReconciliationRecord


def _make_invoice(db, user, amount, confidence, status=InvoiceStatus.EXTRACTED):
    inv = Invoice(
        id=uuid.uuid4(), original_filename="scan.pdf", storage_path="s",
        content_type="application/pdf", uploaded_by=user.id,
        tenant_id=user.tenant_id, status=status,
        total_amount=Decimal(amount), ocr_confidence=confidence,
        invoice_number=f"INV-{uuid.uuid4().hex[:6]}",
    )
    db.add(inv)
    db.commit()
    return inv


def test_low_confidence_invoice_is_held_for_verification(db, admin_user):
    from app.workers.workflow_worker import run_invoice_post_extraction

    inv = _make_invoice(db, admin_user, "500.00", confidence=0.40)

    run_invoice_post_extraction(str(inv.id), db=db)

    reloaded = db.query(Invoice).filter(Invoice.id == inv.id).one()
    assert reloaded.status == InvoiceStatus.NEEDS_VERIFICATION
    assert db.query(ReconciliationRecord).filter(ReconciliationRecord.invoice_id == inv.id).count() == 0


def test_high_confidence_invoice_skips_the_gate_and_reconciles(db, admin_user):
    from app.workers.workflow_worker import run_invoice_post_extraction

    inv = _make_invoice(db, admin_user, "500.00", confidence=0.95)

    run_invoice_post_extraction(str(inv.id), db=db)

    reloaded = db.query(Invoice).filter(Invoice.id == inv.id).one()
    assert reloaded.status != InvoiceStatus.NEEDS_VERIFICATION
    assert db.query(ReconciliationRecord).filter(ReconciliationRecord.invoice_id == inv.id).count() == 1


def test_missing_confidence_is_trusted_not_parked(db, admin_user):
    """No OCR read (manual entry) has nothing to verify against -- it must not
    be treated as low-confidence."""
    from app.workers.workflow_worker import run_invoice_post_extraction

    inv = _make_invoice(db, admin_user, "500.00", confidence=None)

    run_invoice_post_extraction(str(inv.id), db=db)

    reloaded = db.query(Invoice).filter(Invoice.id == inv.id).one()
    assert reloaded.status != InvoiceStatus.NEEDS_VERIFICATION
    assert db.query(ReconciliationRecord).filter(ReconciliationRecord.invoice_id == inv.id).count() == 1


def test_verify_resumes_workflow_and_reconciles(client, db, admin_user, auth_headers):
    inv = _make_invoice(db, admin_user, "500.00", confidence=0.40,
                        status=InvoiceStatus.NEEDS_VERIFICATION)

    resp = client.post(f"/api/v1/invoices/{inv.id}/verify", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] != "needs_verification"

    assert db.query(ReconciliationRecord).filter(ReconciliationRecord.invoice_id == inv.id).count() == 1


def test_verify_low_confidence_high_value_chains_to_approval_gate(client, db, admin_user, auth_headers):
    """Verify confirms the figures; the now-trusted high amount then trips the
    approval gate rather than reconciling straight through."""
    inv = _make_invoice(db, admin_user, "250000.00", confidence=0.40,
                        status=InvoiceStatus.NEEDS_VERIFICATION)

    resp = client.post(f"/api/v1/invoices/{inv.id}/verify", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "pending_approval"
    assert db.query(ReconciliationRecord).filter(ReconciliationRecord.invoice_id == inv.id).count() == 0


def test_cannot_verify_invoice_not_awaiting_verification(client, db, admin_user, auth_headers):
    inv = _make_invoice(db, admin_user, "500.00", confidence=0.95,
                        status=InvoiceStatus.RECONCILED)

    resp = client.post(f"/api/v1/invoices/{inv.id}/verify", headers=auth_headers)
    assert resp.status_code == 400


def test_needs_verification_notifies_accountants(db, admin_user):
    """The verification queue must reach whoever can act on it."""
    from app.workers.workflow_worker import run_invoice_post_extraction

    inv = _make_invoice(db, admin_user, "500.00", confidence=0.40)
    run_invoice_post_extraction(str(inv.id), db=db)

    notes = db.query(Notification).filter(
        Notification.event_name == "invoice.needs_verification",
        Notification.invoice_id == inv.id,
    ).all()
    assert len(notes) >= 1
    assert all(n.tenant_id == admin_user.tenant_id for n in notes)
