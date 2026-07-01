"""In-app notifications: list the caller's own, mark read."""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from app.core.exceptions import not_found
from app.core.rbac import Permission
from app.dependencies import CurrentUser, DBSession, require
from app.models.notification import Notification

router = APIRouter(prefix="/notifications", tags=["Notifications"])


class NotificationResponse(BaseModel):
    id: uuid.UUID
    title: str
    body: str
    event_name: str
    invoice_id: uuid.UUID | None
    read_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


@router.get(
    "",
    response_model=list[NotificationResponse],
    dependencies=[Depends(require(Permission.NOTIFICATION_READ))],
)
def list_notifications(
    current_user: CurrentUser,
    db: DBSession,
    unread_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
):
    """The caller's own notifications -- never another user's, even within
    the same tenant."""
    stmt = select(Notification).where(
        Notification.tenant_id == current_user.tenant_id,
        Notification.user_id == current_user.id,
    )
    if unread_only:
        stmt = stmt.where(Notification.read_at.is_(None))
    stmt = stmt.order_by(Notification.created_at.desc()).limit(limit)
    return db.scalars(stmt).all()


@router.post(
    "/{notification_id}/read",
    response_model=NotificationResponse,
    dependencies=[Depends(require(Permission.NOTIFICATION_READ))],
)
def mark_read(notification_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    notification = db.scalar(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.tenant_id == current_user.tenant_id,
            Notification.user_id == current_user.id,
        )
    )
    if notification is None:
        raise not_found("Notification", str(notification_id))

    if notification.read_at is None:
        notification.read_at = datetime.now(timezone.utc)
        db.commit()
    return notification
