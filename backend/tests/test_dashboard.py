"""Dashboard tests.

Covers BUG-3: the queue-status query computed average processing time with
``func.extract('epoch', completed_at - started_at)``, which is PostgreSQL-only.
On the default SQLite database SQLite has no EXTRACT function, so the dashboard
overview endpoint raised an OperationalError.
"""
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.models.invoice import Invoice, InvoiceStatus
from app.models.processing_job import JobStatus, JobType, ProcessingJob
from app.services.dashboard_service import DashboardService


def test_dashboard_overview_ok_on_sqlite(client, admin_user, auth_headers):
    resp = client.get("/api/v1/dashboard/overview", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "invoice_summary" in body
    assert "queue_status" in body


def test_queue_status_average_processing_time(db, admin_user):
    inv = Invoice(
        id=uuid.uuid4(),
        original_filename="f.pdf",
        storage_path="x",
        content_type="application/pdf",
        status=InvoiceStatus.EXTRACTED,
        total_amount=Decimal("10.00"),
        uploaded_by=admin_user.id,
    )
    db.add(inv)
    started = datetime.now(timezone.utc) - timedelta(seconds=10)
    completed = started + timedelta(seconds=6)
    db.add(
        ProcessingJob(
            invoice_id=inv.id,
            job_type=JobType.OCR_EXTRACTION,
            status=JobStatus.COMPLETED,
            started_at=started,
            completed_at=completed,
        )
    )
    db.commit()

    status = DashboardService(db)._queue_status()

    assert status.average_processing_time_seconds is not None
    assert 5.0 <= status.average_processing_time_seconds <= 7.0
