"""In-app notifications: list the caller's own, mark read."""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select

from app.core.exceptions import not_found
from app.core.rbac import Permission
from app.dependencies import CurrentUser, DBSession, require
from app.models.notification import Notification

router = APIRouter(prefix="/notifications", tags=["Notifications"])


class UnreadCountResponse(BaseModel):
    unread: int


class MarkAllReadResponse(BaseModel):
    marked_read: int


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


@router.get(
    "/unread-count",
    response_model=UnreadCountResponse,
    dependencies=[Depends(require(Permission.NOTIFICATION_READ))],
)
def unread_count(current_user: CurrentUser, db: DBSession):
    """Badge count: the caller's own unread notifications."""
    count = db.scalar(
        select(func.count())
        .select_from(Notification)
        .where(
            Notification.tenant_id == current_user.tenant_id,
            Notification.user_id == current_user.id,
            Notification.read_at.is_(None),
        )
    )
    return UnreadCountResponse(unread=count or 0)


@router.post(
    "/read-all",
    response_model=MarkAllReadResponse,
    dependencies=[Depends(require(Permission.NOTIFICATION_READ))],
)
def mark_all_read(current_user: CurrentUser, db: DBSession):
    """Mark every unread notification for the caller as read; returns how many
    were affected."""
    now = datetime.now(timezone.utc)
    marked = (
        db.query(Notification)
        .filter(
            Notification.tenant_id == current_user.tenant_id,
            Notification.user_id == current_user.id,
            Notification.read_at.is_(None),
        )
        .update({Notification.read_at: now}, synchronize_session=False)
    )
    db.commit()
    return MarkAllReadResponse(marked_read=marked)


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
