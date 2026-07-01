"""Audit-as-event-bus-subscriber convergence (TD-6).

Every service call site that used to write an AuditLog row directly now only
publishes a DomainEvent; the audit row must still show up, produced by the
`"*"` subscriber in app.core.events.audit_subscriber. These tests exist so a
typo in the name -> AuditEventType mapping (which would silently drop an
audit row with no other test noticing) fails loudly.
"""
import uuid

from app.core.events import DomainEvent, event_bus
from app.models.audit_log import AuditEventType, AuditLog


def _last_audit(db, event_type, tenant_id):
    return (
        db.query(AuditLog)
        .filter(AuditLog.event_type == event_type, AuditLog.tenant_id == tenant_id)
        .order_by(AuditLog.created_at.desc())
        .first()
    )


def test_vendor_created_and_updated_produce_audit_rows(db, admin_user):
    from app.schemas.vendor import VendorCreate, VendorUpdate
    from app.services.vendor_service import VendorService

    svc = VendorService(db)
    vendor = svc.create(VendorCreate(name="Acme Co"), admin_user)

    row = _last_audit(db, AuditEventType.VENDOR_CREATED, admin_user.tenant_id)
    assert row is not None
    assert "Acme Co" in row.description

    svc.update(vendor.id, VendorUpdate(name="Acme Corp"), admin_user)
    row = _last_audit(db, AuditEventType.VENDOR_UPDATED, admin_user.tenant_id)
    assert row is not None
    assert "Acme Corp" in row.description


def test_login_produces_audit_row(client, admin_user, db):
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": admin_user.email, "password": "Admin1234"},
    )
    assert resp.status_code == 200

    row = _last_audit(db, AuditEventType.USER_LOGIN, admin_user.tenant_id)
    assert row is not None
    assert row.user_id == admin_user.id


def test_reconciliation_duplicate_and_resolve_produce_audit_rows(db, admin_user):
    from decimal import Decimal

    from app.models.invoice import Invoice, InvoiceStatus
    from app.models.vendor import Vendor
    from app.schemas.reconciliation import ReconciliationRequest, ReconciliationResolveRequest
    from app.services.reconciliation_service import ReconciliationService
    from app.models.reconciliation import ReconciliationStatus

    vendor = Vendor(name="V", normalized_name="v", tenant_id=admin_user.tenant_id)
    db.add(vendor)
    db.flush()

    def _mk_invoice(number):
        inv = Invoice(
            id=uuid.uuid4(), original_filename="f.pdf", storage_path="s",
            content_type="application/pdf", uploaded_by=admin_user.id,
            tenant_id=admin_user.tenant_id, status=InvoiceStatus.EXTRACTED,
            invoice_number=number, vendor_id=vendor.id,
            total_amount=Decimal("100.00"),
        )
        from datetime import date
        inv.invoice_date = date(2026, 1, 1)
        db.add(inv)
        db.flush()
        return inv

    first = _mk_invoice("DUP-1")
    second = _mk_invoice("DUP-1")  # same number/vendor/date -> duplicate
    db.commit()

    svc = ReconciliationService(db)
    rec = svc.reconcile(
        ReconciliationRequest(invoice_id=second.id, notes="test"), admin_user
    )
    dup_row = _last_audit(db, AuditEventType.INVOICE_DUPLICATE_DETECTED, admin_user.tenant_id)
    assert dup_row is not None

    svc.resolve(
        rec.id,
        ReconciliationResolveRequest(
            status=ReconciliationStatus.MANUALLY_RESOLVED, resolution_notes="ok"
        ),
        admin_user,
    )
    resolved_row = _last_audit(db, AuditEventType.RECONCILIATION_RESOLVED, admin_user.tenant_id)
    assert resolved_row is not None


def test_unmapped_event_does_not_create_audit_row_or_raise(db):
    count_before = db.query(AuditLog).count()
    event_bus.publish(db, DomainEvent(name="some.unmapped.event"))
    db.commit()
    assert db.query(AuditLog).count() == count_before
