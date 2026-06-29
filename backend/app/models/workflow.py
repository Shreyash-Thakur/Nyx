import uuid

from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db_types import GUID
from app.models.base import BaseModel
from app.models.tenant import TenantMixin


class WorkflowInstance(TenantMixin, BaseModel):
    """A durable record of one workflow run.

    ``status`` is a free string (running | completed | failed | parked) rather
    than an enum so new lifecycle states don't require a migration.
    """

    __tablename__ = "workflow_instances"

    workflow_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running", index=True)
    current_step: Mapped[str | None] = mapped_column(String(100), nullable=True)
    context: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<WorkflowInstance {self.workflow_name} [{self.status}]>"
