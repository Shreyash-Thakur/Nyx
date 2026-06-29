import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query

from app.core.exceptions import NotFoundError, ValidationError, bad_request, not_found
from app.core.rbac import Permission
from app.dependencies import CurrentUser, DBSession, require
from app.models.reconciliation import DiscrepancyType, ReconciliationStatus
from app.schemas.common import PaginatedResponse
from app.schemas.reconciliation import (
    ReconciliationFilter,
    ReconciliationRecordResponse,
    ReconciliationRequest,
    ReconciliationResolveRequest,
)
from app.services.reconciliation_service import ReconciliationService

import math

router = APIRouter(prefix="/reconciliation", tags=["Reconciliation"])


@router.post(
    "",
    response_model=ReconciliationRecordResponse,
    status_code=201,
    dependencies=[Depends(require(Permission.RECONCILIATION_WRITE))],
)
def reconcile_invoice(
    payload: ReconciliationRequest,
    current_user: CurrentUser,
    db: DBSession,
):
    """Trigger reconciliation for an invoice against a reference document."""
    try:
        record = ReconciliationService(db).reconcile(payload, current_user)
    except (NotFoundError, ValidationError) as exc:
        raise bad_request(exc.message)
    return record


@router.get(
    "",
    response_model=PaginatedResponse[ReconciliationRecordResponse],
    dependencies=[Depends(require(Permission.RECONCILIATION_READ))],
)
def list_reconciliation_records(
    current_user: CurrentUser,
    db: DBSession,
    status: ReconciliationStatus | None = Query(None),
    discrepancy_type: DiscrepancyType | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List reconciliation records with filtering."""
    filters = ReconciliationFilter(
        status=status,
        discrepancy_type=discrepancy_type,
        date_from=date_from,
        date_to=date_to,
    )
    items, total = ReconciliationService(db).list(
        filters, current_user.tenant_id, page=page, page_size=page_size
    )
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


@router.get(
    "/invoice/{invoice_id}",
    response_model=list[ReconciliationRecordResponse],
    dependencies=[Depends(require(Permission.RECONCILIATION_READ))],
)
def get_reconciliation_for_invoice(
    invoice_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
):
    """Get all reconciliation records for a specific invoice."""
    return ReconciliationService(db).get_for_invoice(invoice_id, current_user.tenant_id)


@router.post(
    "/{record_id}/resolve",
    response_model=ReconciliationRecordResponse,
    dependencies=[Depends(require(Permission.RECONCILIATION_WRITE))],
)
def resolve_discrepancy(
    record_id: uuid.UUID,
    payload: ReconciliationResolveRequest,
    current_user: CurrentUser,
    db: DBSession,
):
    """Manually resolve a reconciliation discrepancy."""
    try:
        return ReconciliationService(db).resolve(record_id, payload, current_user)
    except (NotFoundError, ValidationError) as exc:
        raise bad_request(exc.message)
