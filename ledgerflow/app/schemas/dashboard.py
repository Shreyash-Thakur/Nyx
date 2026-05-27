from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class InvoiceCountSummary(BaseModel):
    total: int
    uploaded: int
    processing: int
    extracted: int
    reconciled: int
    failed: int
    duplicate: int


class DiscrepancySummary(BaseModel):
    total_discrepancies: int
    unresolved: int
    resolved: int
    total_discrepancy_amount: Decimal
    by_type: dict[str, int]


class QueueStatus(BaseModel):
    queued_jobs: int
    processing_jobs: int
    failed_jobs: int
    completed_today: int
    average_processing_time_seconds: float | None


class AnalyticsTrend(BaseModel):
    date: date
    invoice_count: int
    total_amount: Decimal
    reconciled_count: int


class VendorMetric(BaseModel):
    vendor_id: str
    vendor_name: str
    invoice_count: int
    total_amount: Decimal
    discrepancy_count: int


class DashboardOverview(BaseModel):
    invoice_summary: InvoiceCountSummary
    discrepancy_summary: DiscrepancySummary
    queue_status: QueueStatus
    top_vendors: list[VendorMetric]
    recent_trends: list[AnalyticsTrend]
    total_processed_amount: Decimal
    pending_payment_amount: Decimal
