"""Activity feed endpoint backed by the durable event log.

Also the first tenant-scoped read: a user only sees events from their tenant.
"""
import uuid

from app.models.event import Event


def _seed_event(db, tenant_id, name="invoice.uploaded"):
    db.add(Event(tenant_id=tenant_id, name=name, aggregate_type="invoice", aggregate_id=uuid.uuid4()))
    db.commit()


def test_activity_returns_recent_events(client, admin_user, auth_headers, db):
    _seed_event(db, admin_user.tenant_id, "invoice.uploaded")
    _seed_event(db, admin_user.tenant_id, "reconciliation.completed")

    resp = client.get("/api/v1/activity", headers=auth_headers)
    assert resp.status_code == 200
    names = {item["name"] for item in resp.json()}
    assert {"invoice.uploaded", "reconciliation.completed"} <= names


def test_activity_is_tenant_scoped(client, admin_user, auth_headers, db):
    _seed_event(db, admin_user.tenant_id, "invoice.uploaded")
    _seed_event(db, uuid.uuid4(), "invoice.uploaded")  # other tenant

    resp = client.get("/api/v1/activity", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1  # only this tenant's event is visible


def test_activity_requires_auth(client):
    assert client.get("/api/v1/activity").status_code == 401
