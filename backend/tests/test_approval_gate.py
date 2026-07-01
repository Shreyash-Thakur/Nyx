"""Finance approval gate (Priority 1: the human-approval pipeline stage).

Invoices over FOUNDER_APPROVAL_THRESHOLD_INR must stop at pending_approval
instead of auto-reconciling; an admin approval resumes the same workflow.
"""
import uuid
from decimal import Decimal

from app.models.invoice import Invoice, InvoiceStatus
from app.models.reconciliation import ReconciliationRecord


def _make_invoice(db, admin_user, amount, status=InvoiceStatus.EXTRACTED):
    inv = Invoice(
        id=uuid.uuid4(), original_filename="big.pdf", storage_path="s",
        content_type="application/pdf", uploaded_by=admin_user.id,
        tenant_id=admin_user.tenant_id, status=status, total_amount=Decimal(amount),
    )
    db.add(inv)
    db.commit()
    return inv


def test_high_value_invoice_is_held_for_approval_not_reconciled(db, admin_user):
    from app.workers.workflow_worker import run_invoice_post_extraction

    inv = _make_invoice(db, admin_user, "250000.00")  # over the 100000 default threshold

    run_invoice_post_extraction(str(inv.id), db=db)

    reloaded = db.query(Invoice).filter(Invoice.id == inv.id).one()
    assert reloaded.status == InvoiceStatus.PENDING_APPROVAL
    assert db.query(ReconciliationRecord).filter(ReconciliationRecord.invoice_id == inv.id).count() == 0


def test_low_value_invoice_skips_the_gate_and_reconciles(db, admin_user):
    from app.workers.workflow_worker import run_invoice_post_extraction

    inv = _make_invoice(db, admin_user, "500.00")

    run_invoice_post_extraction(str(inv.id), db=db)

    reloaded = db.query(Invoice).filter(Invoice.id == inv.id).one()
    assert reloaded.status != InvoiceStatus.PENDING_APPROVAL
    assert db.query(ReconciliationRecord).filter(ReconciliationRecord.invoice_id == inv.id).count() == 1


def test_approve_resumes_the_workflow_and_reconciles(client, db, admin_user, auth_headers):
    inv = _make_invoice(db, admin_user, "250000.00", status=InvoiceStatus.PENDING_APPROVAL)

    resp = client.post(f"/api/v1/invoices/{inv.id}/approve", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] != "pending_approval"

    assert db.query(ReconciliationRecord).filter(ReconciliationRecord.invoice_id == inv.id).count() == 1


def test_reject_marks_invoice_rejected_with_reason(client, db, admin_user, auth_headers):
    inv = _make_invoice(db, admin_user, "250000.00", status=InvoiceStatus.PENDING_APPROVAL)

    resp = client.post(
        f"/api/v1/invoices/{inv.id}/reject",
        json={"reason": "duplicate vendor billing"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"
    assert resp.json()["extraction_notes"] == "duplicate vendor billing"


def test_cannot_approve_invoice_not_pending_approval(client, db, admin_user, auth_headers):
    inv = _make_invoice(db, admin_user, "500.00", status=InvoiceStatus.RECONCILED)

    resp = client.post(f"/api/v1/invoices/{inv.id}/approve", headers=auth_headers)
    assert resp.status_code == 400


def test_accountant_cannot_approve_invoices(client, db, admin_user):
    from app.core.security import hash_password
    from app.models.user import User, UserRole

    accountant = User(
        email="acct_approve@nyxapp.com", full_name="Accountant", role=UserRole.ACCOUNTANT,
        hashed_password=hash_password("Acct12345"), is_active=True, is_verified=True,
    )
    db.add(accountant)
    db.commit()

    login = client.post(
        "/api/v1/auth/login", json={"email": accountant.email, "password": "Acct12345"}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    inv = _make_invoice(db, accountant, "250000.00", status=InvoiceStatus.PENDING_APPROVAL)
    resp = client.post(f"/api/v1/invoices/{inv.id}/approve", headers=headers)
    assert resp.status_code == 403
