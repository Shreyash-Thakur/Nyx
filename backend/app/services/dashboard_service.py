import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.invoice import Invoice, InvoiceStatus, PaymentStatus
from app.models.processing_job import JobStatus, ProcessingJob
from app.models.reconciliation import ReconciliationRecord
from app.models.vendor import Vendor
from app.repositories.invoice_repository import InvoiceRepository
from app.repositories.reconciliation_repository import ReconciliationRepository
from app.schemas.dashboard import (
    AnalyticsTrend,
    DashboardOverview,
    DiscrepancySummary,
    InvoiceCountSummary,
    QueueStatus,
    VendorMetric,
)


class DashboardService:
    def __init__(self, db: Session, tenant_id: uuid.UUID) -> None:
        self.db = db
        self.tenant_id = tenant_id
        self.invoice_repo = InvoiceRepository(db)
        self.recon_repo = ReconciliationRepository(db)

    def get_overview(self) -> DashboardOverview:
        return DashboardOverview(
            invoice_summary=self._invoice_summary(),
            discrepancy_summary=self._discrepancy_summary(),
            queue_status=self._queue_status(),
            top_vendors=self._top_vendors(),
            recent_trends=self._recent_trends(),
            total_processed_amount=self._total_amount(InvoiceStatus.RECONCILED),
            pending_payment_amount=self.invoice_repo.total_amount_by_payment_status(
                PaymentStatus.PENDING, self.tenant_id
            ),
        )

    def _invoice_summary(self) -> InvoiceCountSummary:
        counts = self.invoice_repo.count_by_status(self.tenant_id)
        return InvoiceCountSummary(
            total=sum(counts.values()),
            uploaded=counts.get(InvoiceStatus.UPLOADED.value, 0),
            processing=counts.get(InvoiceStatus.PROCESSING.value, 0),
            extracted=counts.get(InvoiceStatus.EXTRACTED.value, 0),
            needs_verification=counts.get(InvoiceStatus.NEEDS_VERIFICATION.value, 0),
            pending_approval=counts.get(InvoiceStatus.PENDING_APPROVAL.value, 0),
            reconciled=counts.get(InvoiceStatus.RECONCILED.value, 0),
            failed=counts.get(InvoiceStatus.FAILED.value, 0),
            duplicate=counts.get(InvoiceStatus.DUPLICATE.value, 0),
        )

    def _discrepancy_summary(self) -> DiscrepancySummary:
        raw = self.recon_repo.discrepancy_summary(self.tenant_id)
        return DiscrepancySummary(**raw)

    def _queue_status(self) -> QueueStatus:
        def count_jobs(status: JobStatus) -> int:
            return self.db.scalar(
                select(func.count())
                .select_from(ProcessingJob)
                .where(
                    ProcessingJob.status == status,
                    ProcessingJob.tenant_id == self.tenant_id,
                )
            ) or 0

        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        completed_today = self.db.scalar(
            select(func.count())
            .select_from(ProcessingJob)
            .where(
                ProcessingJob.status == JobStatus.COMPLETED,
                ProcessingJob.completed_at >= today_start,
                ProcessingJob.tenant_id == self.tenant_id,
            )
        ) or 0

        # Duration in seconds, computed portably. SQLite has no EXTRACT and no
        # interval arithmetic, so use julianday(); Postgres uses extract(epoch).
        if settings.is_sqlite:
            duration_seconds = (
                func.julianday(ProcessingJob.completed_at)
                - func.julianday(ProcessingJob.started_at)
            ) * 86400.0
        else:
            duration_seconds = func.extract(
                "epoch", ProcessingJob.completed_at - ProcessingJob.started_at
            )

        avg_seconds = self.db.scalar(
            select(func.avg(duration_seconds)).where(
                ProcessingJob.status == JobStatus.COMPLETED,
                ProcessingJob.started_at.isnot(None),
                ProcessingJob.completed_at.isnot(None),
                ProcessingJob.tenant_id == self.tenant_id,
            )
        )

        return QueueStatus(
            queued_jobs=count_jobs(JobStatus.QUEUED),
            processing_jobs=count_jobs(JobStatus.STARTED),
            failed_jobs=count_jobs(JobStatus.FAILED),
            completed_today=completed_today,
            average_processing_time_seconds=round(float(avg_seconds), 1) if avg_seconds else None,
        )

    def _top_vendors(self, limit: int = 5) -> list[VendorMetric]:
        from sqlalchemy import case

        stmt = (
            select(
                Vendor.id.label("vendor_id"),
                Vendor.name.label("vendor_name"),
                func.count(Invoice.id).label("invoice_count"),
                func.coalesce(func.sum(Invoice.total_amount), 0).label("total_amount"),
                func.count(
                    case(
                        (ReconciliationRecord.discrepancy_type.isnot(None), 1),
                        else_=None,
                    )
                ).label("discrepancy_count"),
            )
            .join(Invoice, Invoice.vendor_id == Vendor.id)
            .outerjoin(ReconciliationRecord, ReconciliationRecord.invoice_id == Invoice.id)
            .where(Vendor.tenant_id == self.tenant_id, Invoice.tenant_id == self.tenant_id)
            .group_by(Vendor.id, Vendor.name)
            .order_by(func.sum(Invoice.total_amount).desc().nullslast())
            .limit(limit)
        )
        rows = self.db.execute(stmt).all()
        return [
            VendorMetric(
                vendor_id=str(row.vendor_id),
                vendor_name=row.vendor_name,
                invoice_count=row.invoice_count,
                total_amount=Decimal(str(row.total_amount)),
                discrepancy_count=row.discrepancy_count,
            )
            for row in rows
        ]

    def _recent_trends(self, days: int = 30) -> list[AnalyticsTrend]:
        from sqlalchemy import cast, Date as SADate

        since = datetime.now(timezone.utc).date() - timedelta(days=days)
        stmt = (
            select(
                cast(Invoice.invoice_date, SADate).label("inv_date"),
                func.count(Invoice.id).label("invoice_count"),
                func.coalesce(func.sum(Invoice.total_amount), 0).label("total_amount"),
                func.count(Invoice.id)
                .filter(Invoice.status == InvoiceStatus.RECONCILED)
                .label("reconciled_count"),
            )
            .where(Invoice.invoice_date >= since, Invoice.tenant_id == self.tenant_id)
            .group_by(cast(Invoice.invoice_date, SADate))
            .order_by(cast(Invoice.invoice_date, SADate))
        )
        rows = self.db.execute(stmt).all()
        return [
            AnalyticsTrend(
                date=row.inv_date,
                invoice_count=row.invoice_count,
                total_amount=Decimal(str(row.total_amount)),
                reconciled_count=row.reconciled_count,
            )
            for row in rows
        ]

    def _total_amount(self, status: InvoiceStatus) -> Decimal:
        result = self.db.scalar(
            select(func.coalesce(func.sum(Invoice.total_amount), 0)).where(
                Invoice.status == status, Invoice.tenant_id == self.tenant_id
            )
        )
        return Decimal(str(result or 0))
