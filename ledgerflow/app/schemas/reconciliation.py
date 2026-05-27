from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.reconciliation import DiscrepancyType, ReconciliationStatus


class ReconciliationRecordResponse(BaseModel):
    id: UUID
    invoice_id: UUID
    status: ReconciliationStatus
    discrepancy_type: DiscrepancyType | None
    confidence_score: float | None
    reference_document_id: str | None
    reference_document_type: str | None
    expected_amount: Decimal | None
    actual_amount: Decimal | None
    discrepancy_amount: Decimal | None
    tolerance_applied: Decimal | None
    notes: str | None
    resolution_notes: str | None
    matched_by: UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReconciliationRequest(BaseModel):
    invoice_id: UUID
    reference_document_id: str | None = None
    reference_document_type: str | None = None
    expected_amount: Decimal | None = None
    notes: str | None = None


class ReconciliationResolveRequest(BaseModel):
    resolution_notes: str
    status: ReconciliationStatus


class ReconciliationFilter(BaseModel):
    status: ReconciliationStatus | None = None
    discrepancy_type: DiscrepancyType | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
