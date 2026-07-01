import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db_types import GUID
from app.models.base import BaseModel
from app.models.tenant import TenantMixin


class Notification(TenantMixin, BaseModel):
    """In-app notification for one user, produced by an event-bus subscriber.

    No email/WhatsApp channel yet (those need real external integrations,
    out of scope here) -- this is the in-app channel the architecture doc's
    ``core.notifications.send`` action would eventually dispatch through.
    """

    __tablename__ = "notifications"

    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    event_name: Mapped[str] = mapped_column(String(100), nullable=False)
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True, index=True
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<Notification {self.event_name} -> {self.user_id}>"
