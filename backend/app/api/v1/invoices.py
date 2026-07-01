import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import JSONResponse

from app.core.exceptions import (
    ConflictError,
    NotFoundError,
    ValidationError,
    bad_request,
    conflict,
    not_found,
)
from app.core.rbac import Permission
from app.dependencies import CurrentUser, DBSession, require
from app.models.invoice import InvoiceStatus, PaymentStatus
from app.schemas.common import PaginatedResponse
from app.schemas.invoice import (
    InvoiceDetailResponse,
    InvoiceFilter,
    InvoiceResponse,
    InvoiceUpdate,
    JobStatusResponse,
)
from app.services.invoice_service import InvoiceService

router = APIRouter(prefix="/invoices", tags=["Invoices"])


@router.post(
    "",
    response_model=InvoiceResponse,
    status_code=202,
    dependencies=[Depends(require(Permission.INVOICE_WRITE))],
)
async def upload_invoice(
    file: UploadFile = File(...),
    current_user: CurrentUser = ...,
    db: DBSession = ...,
):
    """Upload a PDF invoice for background OCR processing."""
    try:
        invoice = await InvoiceService(db).upload(file, current_user)
    except ValidationError as exc:
        raise bad_request(exc.message)
    except ConflictError as exc:
        raise conflict(exc.message)
    return invoice


@router.get(
    "",
    response_model=PaginatedResponse[InvoiceResponse],
    dependencies=[Depends(require(Permission.INVOICE_READ))],
)
def list_invoices(
    current_user: CurrentUser,
    db: DBSession,
    status: InvoiceStatus | None = Query(None),
    payment_status: PaymentStatus | None = Query(None),
    vendor_id: uuid.UUID | None = Query(None),
    invoice_number: str | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    amount_min: Decimal | None = Query(None),
    amount_max: Decimal | None = Query(None),
    search: str | None = Query(None, max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List invoices with filtering, search, and pagination."""
    filters = InvoiceFilter(
        status=status,
        payment_status=payment_status,
        vendor_id=vendor_id,
        invoice_number=invoice_number,
        date_from=date_from,
        date_to=date_to,
        amount_min=amount_min,
        amount_max=amount_max,
        search=search,
    )
    items, total = InvoiceService(db).list(
        filters, current_user.tenant_id, page=page, page_size=page_size
    )

    # Enrich with vendor_name
    enriched = []
    for inv in items:
        data = InvoiceResponse.model_validate(inv)
        if inv.vendor:
            data.vendor_name = inv.vendor.name
        enriched.append(data)

    import math
    return PaginatedResponse(
        items=enriched,
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


@router.get(
    "/{invoice_id}",
    response_model=InvoiceDetailResponse,
    dependencies=[Depends(require(Permission.INVOICE_READ))],
)
def get_invoice(invoice_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    """Fetch a single invoice with line items."""
    try:
        invoice = InvoiceService(db).get_detail(invoice_id, current_user.tenant_id)
    except NotFoundError:
        raise not_found("Invoice", str(invoice_id))
    data = InvoiceDetailResponse.model_validate(invoice)
    if invoice.vendor:
        data.vendor_name = invoice.vendor.name
    return data


@router.patch(
    "/{invoice_id}",
    response_model=InvoiceResponse,
    dependencies=[Depends(require(Permission.INVOICE_WRITE))],
)
def update_invoice(
    invoice_id: uuid.UUID,
    payload: InvoiceUpdate,
    current_user: CurrentUser,
    db: DBSession,
):
    """Partially update invoice fields (manual correction)."""
    try:
        invoice = InvoiceService(db).update(invoice_id, payload, current_user)
    except NotFoundError:
        raise not_found("Invoice", str(invoice_id))
    return invoice


@router.get(
    "/{invoice_id}/jobs",
    response_model=list[JobStatusResponse],
    dependencies=[Depends(require(Permission.INVOICE_READ))],
)
def get_invoice_jobs(invoice_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    """Get all processing jobs for an invoice."""
    from sqlalchemy import select
    from app.models.processing_job import ProcessingJob

    jobs = db.scalars(
        select(ProcessingJob)
        .where(
            ProcessingJob.invoice_id == invoice_id,
            ProcessingJob.tenant_id == current_user.tenant_id,
        )
        .order_by(ProcessingJob.created_at.desc())
    ).all()
    return jobs
