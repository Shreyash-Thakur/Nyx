import uuid

from fastapi import APIRouter, Query

from app.core.exceptions import ConflictError, NotFoundError, conflict, not_found
from app.dependencies import CurrentUser, DBSession
from app.schemas.common import PaginatedResponse
from app.schemas.vendor import VendorCreate, VendorResponse, VendorUpdate
from app.services.vendor_service import VendorService

import math

router = APIRouter(prefix="/vendors", tags=["Vendors"])


@router.post("", response_model=VendorResponse, status_code=201)
def create_vendor(payload: VendorCreate, current_user: CurrentUser, db: DBSession):
    """Create a new vendor."""
    try:
        vendor = VendorService(db).create(payload, current_user)
    except ConflictError as exc:
        raise conflict(exc.message)
    return vendor


@router.get("", response_model=PaginatedResponse[VendorResponse])
def list_vendors(
    current_user: CurrentUser,
    db: DBSession,
    search: str | None = Query(None, max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List or search vendors."""
    items, total = VendorService(db).list(search=search, page=page, page_size=page_size)
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


@router.get("/{vendor_id}", response_model=VendorResponse)
def get_vendor(vendor_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    """Fetch a single vendor."""
    try:
        return VendorService(db).get(vendor_id)
    except NotFoundError:
        raise not_found("Vendor", str(vendor_id))


@router.patch("/{vendor_id}", response_model=VendorResponse)
def update_vendor(
    vendor_id: uuid.UUID,
    payload: VendorUpdate,
    current_user: CurrentUser,
    db: DBSession,
):
    """Update vendor details."""
    try:
        return VendorService(db).update(vendor_id, payload, current_user)
    except NotFoundError:
        raise not_found("Vendor", str(vendor_id))
