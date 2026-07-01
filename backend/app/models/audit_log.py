import enum
import uuid
from typing import Any, TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db_types import GUID
from app.models.base import BaseModel
from app.models.tenant import TenantMixin

if TYPE_CHECKING:
    from app.models.invoice import Invoice
    from app.models.user import User


class AuditEventType(str, enum.Enum):
    # Auth events
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    USER_CREATED = "user_created"
    PASSWORD_CHANGED = "password_changed"

    # Invoice lifecycle
    INVOICE_UPLOADED = "invoice_uploaded"
    INVOICE_QUEUED = "invoice_queued"
    INVOICE_PROCESSING_STARTED = "invoice_processing_started"
    INVOICE_PROCESSING_COMPLETED = "invoice_processing_completed"
    INVOICE_PROCESSING_FAILED = "invoice_processing_failed"
    INVOICE_VALIDATED = "invoice_validated"
    INVOICE_UPDATED = "invoice_updated"
    INVOICE_DELETED = "invoice_deleted"
    INVOICE_DUPLICATE_DETECTED = "invoice_duplicate_detected"
    INVOICE_APPROVAL_REQUIRED = "invoice_approval_required"
    INVOICE_APPROVED = "invoice_approved"
    INVOICE_REJECTED = "invoice_rejected"

    # Reconciliation
    RECONCILIATION_STARTED = "reconciliation_started"
    RECONCILIATION_MATCHED = "reconciliation_matched"
    RECONCILIATION_DISCREPANCY = "reconciliation_discrepancy"
    RECONCILIATION_RESOLVED = "reconciliation_resolved"

    # Vendor
    VENDOR_CREATED = "vendor_created"
    VENDOR_UPDATED = "vendor_updated"


class AuditLog(TenantMixin, BaseModel):
    __tablename__ = "audit_logs"

    event_type: Mapped[AuditEventType] = mapped_column(
        Enum(AuditEventType, name="audit_event_type"),
        nullable=False,
        index=True,
    )

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(),
        ForeignKey("invoices.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    description: Mapped[str] = mapped_column(Text, nullable=False)
    extra_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)

    user: Mapped["User | None"] = relationship("User", back_populates="audit_logs")
    invoice: Mapped["Invoice | None"] = relationship("Invoice", back_populates="audit_logs")

    def __repr__(self) -> str:
        return f"<AuditLog {self.event_type} at {self.created_at}>"
