"""Activity feed: a tenant-scoped read over the durable event log.

Backs the dashboard activity panel (replacing a hard-coded array) and is the
seed of the Founder Intelligence event stream.
"""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from app.core.rbac import Permission
from app.dependencies import CurrentUser, DBSession, require
from app.models.event import Event

router = APIRouter(prefix="/activity", tags=["Activity"])


class EventResponse(BaseModel):
    id: uuid.UUID
    name: str
    aggregate_type: str | None
    aggregate_id: uuid.UUID | None
    actor_id: uuid.UUID | None
    payload: dict | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


@router.get(
    "",
    response_model=list[EventResponse],
    dependencies=[Depends(require(Permission.DASHBOARD_READ))],
)
def list_activity(
    current_user: CurrentUser,
    db: DBSession,
    limit: int = Query(20, ge=1, le=100),
):
    """Most recent domain events for the caller's tenant."""
    rows = db.scalars(
        select(Event)
        .where(Event.tenant_id == current_user.tenant_id)
        .order_by(Event.created_at.desc(), Event.id.desc())
        .limit(limit)
    ).all()
    return rows
