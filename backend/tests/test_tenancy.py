"""Tenancy foundation tests (ADR-0008): the schema is tenant-aware and every
write is stamped with the acting principal's tenant, even before tenant
onboarding exists.
"""
import asyncio
import uuid
from decimal import Decimal

from app.core.security import hash_password
from app.core.tenancy import DEFAULT_TENANT_ID, ensure_default_tenant
from app.models.invoice import Invoice, InvoiceStatus
from app.models.tenant import Tenant
from app.models.user import User, UserRole


class _FakeUpload:
    def __init__(self, content: bytes, filename: str, content_type: str):
        self._c = content
        self.filename = filename
        self.content_type = content_type

    async def read(self) -> bytes:
        return self._c


def test_ensure_default_tenant_is_idempotent(db):
    t1 = ensure_default_tenant(db)
    db.commit()
    t2 = ensure_default_tenant(db)
    assert t1.id == t2.id == DEFAULT_TENANT_ID
    assert db.query(Tenant).filter(Tenant.id == DEFAULT_TENANT_ID).count() == 1


def test_invoice_reads_are_tenant_scoped(client, db, admin_user, auth_headers):
    """A user must not see or fetch invoices from another tenant."""
    mine = Invoice(
        id=uuid.uuid4(), original_filename="mine.pdf", storage_path="a",
        content_type="application/pdf", uploaded_by=admin_user.id,
        tenant_id=admin_user.tenant_id,
    )
    theirs = Invoice(
        id=uuid.uuid4(), original_filename="theirs.pdf", storage_path="b",
        content_type="application/pdf", uploaded_by=admin_user.id,
        tenant_id=uuid.uuid4(),  # different tenant
    )
    db.add_all([mine, theirs])
    db.commit()

    listed = client.get("/api/v1/invoices", headers=auth_headers).json()
    assert listed["total"] == 1  # only this tenant's invoice

    # Fetching the other tenant's invoice by id is a 404, not a leak.
    resp = client.get(f"/api/v1/invoices/{theirs.id}", headers=auth_headers)
    assert resp.status_code == 404
    assert client.get(f"/api/v1/invoices/{mine.id}", headers=auth_headers).status_code == 200


def test_vendor_list_is_tenant_scoped(client, db, admin_user, auth_headers):
    from app.models.vendor import Vendor

    db.add(Vendor(name="Mine", normalized_name="mine", tenant_id=admin_user.tenant_id))
    db.add(Vendor(name="Theirs", normalized_name="theirs", tenant_id=uuid.uuid4()))
    db.commit()

    body = client.get("/api/v1/vendors", headers=auth_headers).json()
    assert body["total"] == 1


def test_reconciliation_list_is_tenant_scoped(client, db, admin_user, auth_headers):
    from app.models.reconciliation import ReconciliationRecord, ReconciliationStatus

    inv_mine = Invoice(
        id=uuid.uuid4(), original_filename="m.pdf", storage_path="m",
        content_type="application/pdf", uploaded_by=admin_user.id,
        tenant_id=admin_user.tenant_id,
    )
    db.add(inv_mine)
    db.flush()
    db.add(ReconciliationRecord(invoice_id=inv_mine.id, status=ReconciliationStatus.PENDING,
                                tenant_id=admin_user.tenant_id))
    db.add(ReconciliationRecord(invoice_id=inv_mine.id, status=ReconciliationStatus.PENDING,
                                tenant_id=uuid.uuid4()))
    db.commit()

    body = client.get("/api/v1/reconciliation", headers=auth_headers).json()
    assert body["total"] == 1


def test_invoice_patch_is_tenant_scoped(client, db, admin_user, auth_headers):
    """A user must not be able to PATCH another tenant's invoice by id."""
    theirs = Invoice(
        id=uuid.uuid4(), original_filename="theirs.pdf", storage_path="b",
        content_type="application/pdf", uploaded_by=admin_user.id,
        tenant_id=uuid.uuid4(),
    )
    db.add(theirs)
    db.commit()

    resp = client.patch(
        f"/api/v1/invoices/{theirs.id}",
        json={"invoice_number": "HACKED-001"},
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_vendor_get_and_update_are_tenant_scoped(client, db, admin_user, auth_headers):
    from app.models.vendor import Vendor

    theirs = Vendor(name="Theirs", normalized_name="theirs", tenant_id=uuid.uuid4())
    db.add(theirs)
    db.commit()

    assert client.get(f"/api/v1/vendors/{theirs.id}", headers=auth_headers).status_code == 404
    resp = client.patch(
        f"/api/v1/vendors/{theirs.id}", json={"name": "Hacked"}, headers=auth_headers
    )
    assert resp.status_code == 404


def test_reconciliation_resolve_is_tenant_scoped(client, db, admin_user, auth_headers):
    from app.models.reconciliation import ReconciliationRecord, ReconciliationStatus

    other_tenant_invoice = Invoice(
        id=uuid.uuid4(), original_filename="o.pdf", storage_path="o",
        content_type="application/pdf", uploaded_by=admin_user.id,
        tenant_id=uuid.uuid4(),
    )
    db.add(other_tenant_invoice)
    db.flush()
    theirs = ReconciliationRecord(
        invoice_id=other_tenant_invoice.id,
        status=ReconciliationStatus.PENDING,
        tenant_id=other_tenant_invoice.tenant_id,
    )
    db.add(theirs)
    db.commit()

    resp = client.post(
        f"/api/v1/reconciliation/{theirs.id}/resolve",
        json={"status": "manually_resolved", "resolution_notes": "hacked"},
        headers=auth_headers,
    )
    assert resp.status_code in (400, 404)


def test_dashboard_overview_excludes_other_tenants(client, db, admin_user, auth_headers):
    """Dashboard aggregates must not fold in another tenant's invoices/amounts."""
    from app.models.vendor import Vendor

    other_tenant = uuid.uuid4()
    other_vendor = Vendor(name="OtherCo", normalized_name="otherco", tenant_id=other_tenant)
    db.add(other_vendor)
    db.flush()
    other_invoice = Invoice(
        id=uuid.uuid4(), original_filename="big.pdf", storage_path="big",
        content_type="application/pdf", uploaded_by=admin_user.id,
        tenant_id=other_tenant, vendor_id=other_vendor.id,
        total_amount=Decimal("999999.00"), status=InvoiceStatus.RECONCILED,
    )
    db.add(other_invoice)
    db.commit()

    body = client.get("/api/v1/dashboard/overview", headers=auth_headers).json()
    assert body["invoice_summary"]["total"] == 0
    assert Decimal(str(body["total_processed_amount"])) == Decimal("0")
    assert body["top_vendors"] == []


def test_upload_stamps_uploader_tenant(db, mocker):
    other_tenant = uuid.uuid4()
    user = User(
        email="t@example.com",
        full_name="Tenant User",
        hashed_password=hash_password("Password123"),
        role=UserRole.ADMIN,
        is_active=True,
        tenant_id=other_tenant,
    )
    db.add(user)
    db.commit()

    mocker.patch(
        "app.services.invoice_service.StorageService.save",
        return_value=("invoices/2026/06/x/t.pdf", "checksum-tenant-test"),
    )
    mocker.patch(
        "app.services.invoice_service.enqueue_ocr_job",
        return_value=None,
    )

    from app.services.invoice_service import InvoiceService

    inv = asyncio.run(
        InvoiceService(db).upload(_FakeUpload(b"%PDF-1.4 x", "t.pdf", "application/pdf"), user)
    )

    assert inv.tenant_id == other_tenant

    # Child rows created in the same flow inherit the invoice's tenant.
    from app.models.processing_job import ProcessingJob

    job = db.query(ProcessingJob).filter(ProcessingJob.invoice_id == inv.id).one()
    assert job.tenant_id == other_tenant
