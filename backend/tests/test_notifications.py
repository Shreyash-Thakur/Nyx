"""Minimal notification engine: event-bus subscribers -> in-app rows -> API."""
import uuid
from decimal import Decimal

from app.models.invoice import Invoice, InvoiceStatus
from app.models.notification import Notification


def _make_invoice(db, admin_user, amount="250000.00", status=InvoiceStatus.PENDING_APPROVAL):
    inv = Invoice(
        id=uuid.uuid4(), original_filename="f.pdf", storage_path="s",
        content_type="application/pdf", uploaded_by=admin_user.id,
        tenant_id=admin_user.tenant_id, status=status, total_amount=Decimal(amount),
    )
    db.add(inv)
    db.commit()
    return inv


def test_approval_required_notifies_admins(db, admin_user):
    from app.workers.workflow_worker import run_invoice_post_extraction

    inv = _make_invoice(db, admin_user, "250000.00", status=InvoiceStatus.EXTRACTED)
    run_invoice_post_extraction(str(inv.id), db=db)

    rows = db.query(Notification).filter(
        Notification.event_name == "invoice.approval_required",
        Notification.user_id == admin_user.id,
    ).all()
    assert len(rows) == 1
    assert rows[0].invoice_id == inv.id
    assert rows[0].read_at is None


def test_rejection_notifies_the_uploader(client, db, admin_user, auth_headers):
    inv = _make_invoice(db, admin_user)

    resp = client.post(
        f"/api/v1/invoices/{inv.id}/reject",
        json={"reason": "bad vendor"},
        headers=auth_headers,
    )
    assert resp.status_code == 200

    row = db.query(Notification).filter(
        Notification.event_name == "invoice.rejected",
        Notification.user_id == admin_user.id,  # admin_user is the uploader here
    ).first()
    assert row is not None
    assert "bad vendor" in row.body


def test_list_and_mark_read(client, db, admin_user, auth_headers):
    inv = _make_invoice(db, admin_user)
    db.add(Notification(
        tenant_id=admin_user.tenant_id, user_id=admin_user.id, title="t", body="b",
        event_name="invoice.approval_required", invoice_id=inv.id,
    ))
    db.commit()

    resp = client.get("/api/v1/notifications", headers=auth_headers)
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["read_at"] is None

    notif_id = items[0]["id"]
    resp2 = client.post(f"/api/v1/notifications/{notif_id}/read", headers=auth_headers)
    assert resp2.status_code == 200
    assert resp2.json()["read_at"] is not None

    unread = client.get("/api/v1/notifications?unread_only=true", headers=auth_headers).json()
    assert unread == []


def test_notifications_are_scoped_to_the_caller_not_just_the_tenant(client, db, admin_user, auth_headers):
    """Another user in the same tenant must not see this user's notifications."""
    other_user_id = uuid.uuid4()
    db.add(Notification(
        tenant_id=admin_user.tenant_id, user_id=other_user_id, title="t", body="b",
        event_name="invoice.approval_required",
    ))
    db.commit()

    resp = client.get("/api/v1/notifications", headers=auth_headers)
    assert resp.json() == []


def test_unread_count_and_mark_all_read(client, db, admin_user, auth_headers):
    for i in range(3):
        db.add(Notification(
            tenant_id=admin_user.tenant_id, user_id=admin_user.id,
            title=f"t{i}", body="b", event_name="invoice.approval_required",
        ))
    db.commit()

    # Badge count reflects the three unread.
    assert client.get("/api/v1/notifications/unread-count", headers=auth_headers).json()["unread"] == 3

    # Mark-all-read clears them and reports how many were affected.
    resp = client.post("/api/v1/notifications/read-all", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["marked_read"] == 3

    assert client.get("/api/v1/notifications/unread-count", headers=auth_headers).json()["unread"] == 0
    # Idempotent: a second call marks nothing.
    assert client.post("/api/v1/notifications/read-all", headers=auth_headers).json()["marked_read"] == 0


def test_unread_count_is_scoped_to_the_caller(client, db, admin_user, auth_headers):
    """Another user's unread notifications must not inflate this user's badge."""
    db.add(Notification(
        tenant_id=admin_user.tenant_id, user_id=uuid.uuid4(), title="t", body="b",
        event_name="invoice.approval_required",
    ))
    db.commit()
    assert client.get("/api/v1/notifications/unread-count", headers=auth_headers).json()["unread"] == 0


def test_notifications_require_authentication(client):
    assert client.get("/api/v1/notifications").status_code == 401
