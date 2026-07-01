import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query

from app.core.rbac import Permission
from app.dependencies import CurrentUser, DBSession, require
from app.models.audit_log import AuditEventType, AuditLog
from app.repositories.audit_repository import AuditRepository
from app.schemas.common import PaginatedResponse

import math
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class AuditLogResponse(BaseModel):
    id: uuid.UUID
    event_type: AuditEventType
    user_id: uuid.UUID | None
    invoice_id: uuid.UUID | None
    description: str
    # Maps to AuditLog.extra_data (the column was renamed from `metadata`);
    # exposed to clients as `metadata` via an alias.
    extra_data: dict | None = None
    ip_address: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


router = APIRouter(prefix="/audit", tags=["Audit Logs"])


@router.get(
    "",
    response_model=PaginatedResponse[AuditLogResponse],
    dependencies=[Depends(require(Permission.AUDIT_READ))],
)
def list_audit_logs(
    current_user: CurrentUser,
    db: DBSession,
    user_id: uuid.UUID | None = Query(None),
    invoice_id: uuid.UUID | None = Query(None),
    event_type: AuditEventType | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """Query audit logs. Admins can view all; others see their own."""
    from app.models.user import UserRole

    effective_user_id = user_id
    if current_user.role != UserRole.ADMIN:
        effective_user_id = current_user.id

    items, total = AuditRepository(db).list_paginated(
        tenant_id=current_user.tenant_id,
        user_id=effective_user_id,
        invoice_id=invoice_id,
        event_type=event_type,
        date_from=date_from,
        date_to=date_to,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )
