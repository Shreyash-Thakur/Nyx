"""Worker pipeline tests.

Covers BUG-2: the automatic reconciliation worker attributed its action to a
hard-coded system-user UUID that did not exist in the ``users`` table. With
foreign-key enforcement on (SQLite PRAGMA + always on Postgres) the insert of
``reconciliation_records.matched_by`` / ``audit_logs.user_id`` raised an
IntegrityError, so auto-reconciliation failed for every invoice.

The worker functions accept an optional ``db`` session for testability so the
job logic can be exercised against the test database session.
"""
import uuid
from decimal import Decimal

from app.models.invoice import Invoice, InvoiceStatus
from app.models.reconciliation import ReconciliationRecord
from app.models.user import User
from app.workers.reconciliation_worker import auto_reconcile


def _make_invoice(db, admin_user, **overrides) -> Invoice:
    defaults = dict(
        id=uuid.uuid4(),
        original_filename="invoice.pdf",
        storage_path="invoices/2026/06/x/invoice.pdf",
        content_type="application/pdf",
        status=InvoiceStatus.EXTRACTED,
        total_amount=Decimal("100.00"),
        uploaded_by=admin_user.id,
    )
    defaults.update(overrides)
    inv = Invoice(**defaults)
    db.add(inv)
    db.commit()
    return inv


def test_auto_reconcile_creates_record_without_fk_error(db, admin_user):
    inv = _make_invoice(db, admin_user)

    result = auto_reconcile(str(inv.id), db=db)

    assert result["status"] != "skipped"
    records = (
        db.query(ReconciliationRecord)
        .filter(ReconciliationRecord.invoice_id == inv.id)
        .all()
    )
    assert len(records) == 1


def test_auto_reconcile_attributes_to_a_real_system_user(db, admin_user):
    inv = _make_invoice(db, admin_user)

    auto_reconcile(str(inv.id), db=db)

    record = (
        db.query(ReconciliationRecord)
        .filter(ReconciliationRecord.invoice_id == inv.id)
        .one()
    )
    # matched_by must reference a user row that actually exists (FK integrity).
    assert record.matched_by is not None
    system_user = db.get(User, record.matched_by)
    assert system_user is not None


def test_auto_reconcile_skips_non_extracted_invoice(db, admin_user):
    inv = _make_invoice(db, admin_user, status=InvoiceStatus.RECONCILED)

    result = auto_reconcile(str(inv.id), db=db)

    assert result["status"] == "skipped"
