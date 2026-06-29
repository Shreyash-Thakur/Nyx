import uuid

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db_types import GUID
from app.models.base import BaseModel
from app.models.tenant import TenantMixin


class Event(TenantMixin, BaseModel):
    """Durable, replayable record of a domain event.

    ``created_at`` (from BaseModel) is the occurrence time. The append-only log
    is the source of truth subscribers and future async relays read from.
    """

    __tablename__ = "events"

    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    aggregate_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    aggregate_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True, index=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    def __repr__(self) -> str:
        return f"<Event {self.name} {self.aggregate_type}:{self.aggregate_id}>"
