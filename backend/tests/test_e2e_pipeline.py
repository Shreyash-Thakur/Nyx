"""End-to-end pipeline tests (Priority 6 & 7).

These exercise the *whole* connected pipeline through real HTTP + the real
worker/workflow/event code, mocking only the two genuinely external edges:
OCR text extraction (needs tesseract) and blob storage I/O. Everything in
between -- upload, dedup, extraction application, the workflow engine, both
gates, reconciliation, the event bus, the audit and notification subscribers,
and the Tally export -- runs for real, inline.

The point is to prove Priority 1: a real invoice flows Upload -> OCR ->
Extraction -> Workflow -> (gates) -> Reconciliation -> Accounting export,
with the audit trail, dashboard and events all updating as a side effect.
"""
import hashlib
import io
import uuid
from decimal import Decimal

import pytest

from app.models.audit_log import AuditEventType, AuditLog
from app.models.event import Event
from app.models.invoice import Invoice, InvoiceStatus
from app.models.reconciliation import ReconciliationRecord
from app.services.ocr_service import ExtractedInvoiceData

SAMPLE_PDF = b"%PDF-1.4 fake invoice bytes"


@pytest.fixture()
def wired_pipeline(mocker):
    """Wire the external edges (storage + OCR) so the inline pipeline runs
    deterministically. Returns a setter for the extraction the OCR step yields
    so each test controls confidence / amount / fields."""
    store: dict[str, bytes] = {}

    async def fake_save(content, filename, invoice_id, content_type):
        checksum = hashlib.sha256(content).hexdigest()
        path = f"invoices/{invoice_id}/{filename}"
        store[path] = content
        return path, checksum

    mocker.patch(
        "app.services.invoice_service.StorageService.save", side_effect=fake_save
    )
    mocker.patch(
        "app.workers.invoice_processor._storage_service.read_sync",
        side_effect=lambda path: store.get(path, SAMPLE_PDF),
    )

    holder: dict[str, ExtractedInvoiceData] = {
        "data": ExtractedInvoiceData(
            invoice_number="INV-E2E-001",
            vendor_name="Acme Supplies",
            total_amount=Decimal("5000.00"),
            subtotal=Decimal("5000.00"),
            confidence=0.95,
            raw_text="fake",
        )
    }
    mocker.patch(
        "app.workers.invoice_processor._ocr_service.extract_from_pdf",
        side_effect=lambda pdf_bytes: holder["data"],
    )

    def set_extraction(data: ExtractedInvoiceData) -> None:
        holder["data"] = data

    return set_extraction


def _upload(client, headers, content=SAMPLE_PDF, filename="invoice.pdf"):
    return client.post(
        "/api/v1/invoices",
        files={"file": (filename, io.BytesIO(content), "application/pdf")},
        headers=headers,
    )


def test_full_pipeline_upload_to_reconciled_and_exported(
    client, db, admin_user, auth_headers, wired_pipeline
):
    resp = _upload(client, auth_headers)
    assert resp.status_code == 202
    invoice_id = resp.json()["id"]

    # The inline pipeline ran to completion during the request: a trustworthy,
    # low-value invoice auto-reconciles with no human in the loop.
    inv = db.query(Invoice).filter(Invoice.id == uuid.UUID(invoice_id)).one()
    assert inv.status == InvoiceStatus.RECONCILED
    assert inv.invoice_number == "INV-E2E-001"

    assert db.query(ReconciliationRecord).filter(
        ReconciliationRecord.invoice_id == inv.id
    ).count() == 1

    # Accounting export is reachable for the reconciled invoice.
    exp = client.get(f"/api/v1/invoices/{invoice_id}/tally-export", headers=auth_headers)
    assert exp.status_code == 200
    assert "<ENVELOPE>" in exp.json()["xml"] or "<TALLYMESSAGE" in exp.json()["xml"].upper()

    # Dashboard reflects the reconciled invoice.
    dash = client.get("/api/v1/dashboard/overview", headers=auth_headers).json()
    assert dash["invoice_summary"]["reconciled"] == 1


def test_pipeline_emits_events_and_audit_at_each_stage(
    client, db, admin_user, auth_headers, wired_pipeline
):
    resp = _upload(client, auth_headers)
    invoice_id = uuid.UUID(resp.json()["id"])

    event_names = {
        e.name for e in db.query(Event).filter(Event.aggregate_id == invoice_id).all()
    }
    assert "invoice.uploaded" in event_names
    assert "invoice.extracted" in event_names
    assert "reconciliation.completed" in event_names

    # The audit subscriber turned those same events into audit rows (one write,
    # two views) -- so upload and extraction both appear in the audit trail.
    audit_types = {
        a.event_type
        for a in db.query(AuditLog).filter(AuditLog.invoice_id == invoice_id).all()
    }
    assert AuditEventType.INVOICE_UPLOADED in audit_types
    assert AuditEventType.INVOICE_PROCESSING_COMPLETED in audit_types


def test_low_confidence_invoice_parks_at_verification_end_to_end(
    client, db, admin_user, auth_headers, wired_pipeline
):
    wired_pipeline(
        ExtractedInvoiceData(
            invoice_number="INV-LOWCONF",
            vendor_name="Blurry Scan Co",
            total_amount=Decimal("5000.00"),
            confidence=0.30,  # below the verify threshold
            raw_text="blurry",
        )
    )
    resp = _upload(client, auth_headers)
    invoice_id = uuid.UUID(resp.json()["id"])

    inv = db.query(Invoice).filter(Invoice.id == invoice_id).one()
    assert inv.status == InvoiceStatus.NEEDS_VERIFICATION
    assert db.query(ReconciliationRecord).filter(
        ReconciliationRecord.invoice_id == inv.id
    ).count() == 0

    # A human verify drives it the rest of the way to reconciled.
    v = client.post(f"/api/v1/invoices/{invoice_id}/verify", headers=auth_headers)
    assert v.status_code == 200
    assert db.query(ReconciliationRecord).filter(
        ReconciliationRecord.invoice_id == invoice_id
    ).count() == 1


def test_high_value_invoice_parks_at_approval_end_to_end(
    client, db, admin_user, auth_headers, wired_pipeline
):
    wired_pipeline(
        ExtractedInvoiceData(
            invoice_number="INV-BIG",
            vendor_name="Big Ticket Ltd",
            total_amount=Decimal("500000.00"),  # over approval threshold
            confidence=0.95,
            raw_text="big",
        )
    )
    resp = _upload(client, auth_headers)
    invoice_id = uuid.UUID(resp.json()["id"])

    inv = db.query(Invoice).filter(Invoice.id == invoice_id).one()
    assert inv.status == InvoiceStatus.PENDING_APPROVAL
    assert db.query(ReconciliationRecord).filter(
        ReconciliationRecord.invoice_id == inv.id
    ).count() == 0


# ── Adversarial: try to break it (Priority 7) ───────────────────────────────

def test_duplicate_upload_is_rejected(client, db, admin_user, auth_headers, wired_pipeline):
    """Same bytes twice -> same checksum -> 409, no second invoice row."""
    first = _upload(client, auth_headers, content=b"identical-invoice-bytes")
    assert first.status_code == 202

    dup = _upload(client, auth_headers, content=b"identical-invoice-bytes")
    assert dup.status_code == 409

    # Different content is accepted (checksum differs).
    other = _upload(client, auth_headers, content=b"a-different-invoice")
    assert other.status_code == 202


def test_empty_file_is_rejected(client, admin_user, auth_headers, wired_pipeline):
    resp = _upload(client, auth_headers, content=b"")
    assert resp.status_code == 400


def test_cross_tenant_verify_is_404_not_a_leak(client, db, admin_user, auth_headers):
    """The new verify endpoint must be tenant-scoped like every other by-id op."""
    theirs = Invoice(
        id=uuid.uuid4(), original_filename="theirs.pdf", storage_path="x",
        content_type="application/pdf", uploaded_by=admin_user.id,
        tenant_id=uuid.uuid4(),  # a different tenant
        status=InvoiceStatus.NEEDS_VERIFICATION,
    )
    db.add(theirs)
    db.commit()

    resp = client.post(f"/api/v1/invoices/{theirs.id}/verify", headers=auth_headers)
    assert resp.status_code == 404


def test_malformed_extraction_does_not_crash_pipeline(
    client, db, admin_user, auth_headers, wired_pipeline
):
    """OCR that finds nothing usable must leave the invoice in a clean state,
    not raise or half-commit. With no invoice number the post-extraction
    workflow isn't even enqueued, so it simply rests at extracted."""
    wired_pipeline(ExtractedInvoiceData(confidence=0.0, raw_text=""))

    resp = _upload(client, auth_headers)
    assert resp.status_code == 202
    invoice_id = uuid.UUID(resp.json()["id"])

    inv = db.query(Invoice).filter(Invoice.id == invoice_id).one()
    assert inv.status == InvoiceStatus.EXTRACTED
    assert db.query(ReconciliationRecord).filter(
        ReconciliationRecord.invoice_id == inv.id
    ).count() == 0
