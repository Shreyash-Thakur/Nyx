from fastapi import APIRouter

from app.dependencies import CurrentUser, DBSession
from app.schemas.dashboard import (
    AnalyticsTrend,
    DashboardOverview,
    DiscrepancySummary,
    InvoiceCountSummary,
    QueueStatus,
)
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/overview", response_model=DashboardOverview)
def get_overview(current_user: CurrentUser, db: DBSession):
    """Full dashboard overview: invoice metrics, queue status, trends."""
    return DashboardService(db).get_overview()


@router.get("/invoices/summary", response_model=InvoiceCountSummary)
def invoice_summary(current_user: CurrentUser, db: DBSession):
    """Invoice status counts."""
    return DashboardService(db)._invoice_summary()


@router.get("/discrepancies/summary", response_model=DiscrepancySummary)
def discrepancy_summary(current_user: CurrentUser, db: DBSession):
    """Discrepancy breakdown by type and resolution status."""
    return DashboardService(db)._discrepancy_summary()


@router.get("/queue/status", response_model=QueueStatus)
def queue_status(current_user: CurrentUser, db: DBSession):
    """Current processing queue depth and throughput."""
    return DashboardService(db)._queue_status()


@router.get("/analytics/trends", response_model=list[AnalyticsTrend])
def analytics_trends(current_user: CurrentUser, db: DBSession):
    """30-day invoice volume and amount trends."""
    return DashboardService(db)._recent_trends()
