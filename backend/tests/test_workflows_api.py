"""Workflow instance API: listing and retrying failed instances."""
import uuid


def _seed_failed_instance(db, tenant_id):
    from app.models.workflow import WorkflowInstance

    instance = WorkflowInstance(
        tenant_id=tenant_id,
        workflow_name="invoice_post_extraction",
        status="failed",
        current_step="reconcile",
        context={"invoice_id": str(uuid.uuid4()), "status": "extracted"},
        error="boom",
    )
    db.add(instance)
    db.commit()
    db.refresh(instance)
    return instance


def test_list_instances_requires_admin_permission(client, db, admin_user, auth_headers):
    _seed_failed_instance(db, admin_user.tenant_id)
    resp = client.get("/api/v1/workflows/instances", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["status"] == "failed"


def test_instances_are_tenant_scoped(client, db, admin_user, auth_headers):
    _seed_failed_instance(db, uuid.uuid4())  # another tenant
    resp = client.get("/api/v1/workflows/instances", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == []


def test_retry_unknown_instance_is_404(client, admin_user, auth_headers):
    resp = client.post(
        f"/api/v1/workflows/instances/{uuid.uuid4()}/retry", headers=auth_headers
    )
    assert resp.status_code == 404


def test_retry_reruns_the_workflow_and_reconciles(client, db, admin_user, auth_headers):
    from decimal import Decimal

    from app.models.invoice import Invoice, InvoiceStatus
    from app.models.reconciliation import ReconciliationRecord

    inv = Invoice(
        id=uuid.uuid4(), original_filename="f.pdf", storage_path="s",
        content_type="application/pdf", uploaded_by=admin_user.id,
        tenant_id=admin_user.tenant_id, status=InvoiceStatus.EXTRACTED,
        total_amount=Decimal("50.00"),
    )
    db.add(inv)
    db.commit()

    instance = _seed_failed_instance(db, admin_user.tenant_id)
    instance.context = {"invoice_id": str(inv.id), "status": "extracted"}
    db.commit()

    resp = client.post(
        f"/api/v1/workflows/instances/{instance.id}/retry", headers=auth_headers
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"

    records = db.query(ReconciliationRecord).filter(ReconciliationRecord.invoice_id == inv.id).all()
    assert len(records) == 1


def test_viewer_cannot_retry_workflows(client, db):
    from app.core.security import hash_password
    from app.models.user import User, UserRole

    viewer = User(
        email="viewer_wf@nyxapp.com", full_name="Viewer", role=UserRole.VIEWER,
        hashed_password=hash_password("Viewer1234"), is_active=True, is_verified=True,
    )
    db.add(viewer)
    db.commit()

    login = client.post(
        "/api/v1/auth/login", json={"email": viewer.email, "password": "Viewer1234"}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    instance = _seed_failed_instance(db, viewer.tenant_id)
    resp = client.post(f"/api/v1/workflows/instances/{instance.id}/retry", headers=headers)
    assert resp.status_code == 403
