"""Worker pipeline tests.

Covers BUG-2: automatic reconciliation attributed its action to a hard-coded
system-user UUID that did not exist in the ``users`` table. With foreign-key
enforcement on (SQLite PRAGMA + always on Postgres) the insert of
``reconciliation_records.matched_by`` / ``audit_logs.user_id`` raised an
IntegrityError, so auto-reconciliation failed for every invoice. The fix
(``ensure_system_user``) lives in the ``accounts.reconcile_invoice`` workflow
action now, exercised here via the ``invoice_post_extraction`` workflow --
the same path production uses, since the old bespoke
``reconciliation_worker.auto_reconcile`` job was retired in favor of running
the workflow engine directly (no more duplicate execution path).

The worker function accepts an optional ``db`` session for testability so the
job logic can be exercised against the test database session.
"""
import uuid
from decimal import Decimal

from app.models.invoice import Invoice, InvoiceStatus
from app.models.reconciliation import ReconciliationRecord
from app.models.user import User
from app.workers.workflow_worker import run_invoice_post_extraction


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

    result = run_invoice_post_extraction(str(inv.id), db=db)

    assert result["workflow_status"] == "completed"
    assert "reconciliation_status" in result["context"]
    records = (
        db.query(ReconciliationRecord)
        .filter(ReconciliationRecord.invoice_id == inv.id)
        .all()
    )
    assert len(records) == 1


def test_auto_reconcile_attributes_to_a_real_system_user(db, admin_user):
    inv = _make_invoice(db, admin_user)

    run_invoice_post_extraction(str(inv.id), db=db)

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

    result = run_invoice_post_extraction(str(inv.id), db=db)

    assert result["workflow_status"] == "completed"
    assert "reconciliation_status" not in result["context"]  # step was skipped


def test_ocr_worker_advances_through_the_workflow_engine(db, admin_user, mocker):
    """End-to-end at the worker layer: OCR completion must reach reconciliation
    via the workflow engine (app.core.workflow), not a parallel hand-written
    call. This is the pipeline stage Priority 2 asked to be de-duplicated."""
    import types

    from app.models.processing_job import JobStatus, JobType, ProcessingJob
    from app.models.workflow import WorkflowInstance
    from app.workers import invoice_processor, workflow_worker

    inv = Invoice(
        id=uuid.uuid4(), original_filename="ocr.pdf", storage_path="s/ocr.pdf",
        content_type="application/pdf", uploaded_by=admin_user.id,
        tenant_id=admin_user.tenant_id, status=InvoiceStatus.QUEUED,
    )
    db.add(inv)
    db.flush()
    job = ProcessingJob(invoice_id=inv.id, tenant_id=inv.tenant_id, job_type=JobType.OCR_EXTRACTION)
    db.add(job)
    db.commit()
    # process_invoice() closes its (patched-to-be-shared) session in a
    # `finally`, which detaches and expires previously loaded objects -- grab
    # plain values now rather than touching ORM attributes afterwards.
    inv_id, tenant_id, job_id = inv.id, inv.tenant_id, job.id

    fake_extracted = types.SimpleNamespace(
        invoice_number="INV-777", vendor_name=None, invoice_date=None, due_date=None,
        subtotal=None, cgst_amount=None, sgst_amount=None, igst_amount=None,
        total_tax=None, total_amount=Decimal("500.00"), currency="INR",
        line_items=[], confidence=0.9, raw_text="raw",
    )
    # The queue is 'inline' in tests, which would open a second, unrelated
    # SessionLocal() against a bare in-memory SQLite DB (the "two-engine
    # split" noted in STATUS.md). Route the enqueue straight through the
    # workflow worker on this test's session instead of via a fresh one.
    mocker.patch.object(invoice_processor, "SessionLocal", return_value=db)
    mocker.patch.object(invoice_processor._storage_service, "read_sync", return_value=b"%PDF")
    mocker.patch.object(invoice_processor._ocr_service, "extract_from_pdf", return_value=fake_extracted)
    mocker.patch(
        "app.workers.queue.enqueue_post_extraction_workflow_job",
        side_effect=lambda invoice_id: workflow_worker.run_invoice_post_extraction(invoice_id, db=db),
    )

    invoice_processor.process_invoice(str(inv_id), str(job_id))

    reloaded = db.query(Invoice).filter(Invoice.id == inv_id).one()
    assert reloaded.status == InvoiceStatus.VALIDATED  # reconciled via the workflow (no expected_amount to match)

    instances = db.query(WorkflowInstance).filter(WorkflowInstance.tenant_id == tenant_id).all()
    assert any(i.workflow_name == "invoice_post_extraction" and i.status == "completed" for i in instances)

    records = db.query(ReconciliationRecord).filter(ReconciliationRecord.invoice_id == inv_id).all()
    assert len(records) == 1
