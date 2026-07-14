import enum
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, ForeignKey, Index, Numeric, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db_types import GUID, db_enum
from app.models.base import BaseModel
from app.models.tenant import TenantMixin

if TYPE_CHECKING:
    from app.models.audit_log import AuditLog
    from app.models.invoice_item import InvoiceItem
    from app.models.processing_job import ProcessingJob
    from app.models.reconciliation import ReconciliationRecord
    from app.models.user import User
    from app.models.vendor import Vendor


class InvoiceStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    QUEUED = "queued"
    PROCESSING = "processing"
    EXTRACTED = "extracted"
    NEEDS_VERIFICATION = "needs_verification"
    VALIDATED = "validated"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    RECONCILED = "reconciled"
    FAILED = "failed"
    DUPLICATE = "duplicate"


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    PAID = "paid"
    OVERDUE = "overdue"
    PARTIAL = "partial"
    CANCELLED = "cancelled"


class Invoice(TenantMixin, BaseModel):
    __tablename__ = "invoices"
    # Race-safe duplicate-upload guard (SEC-4): the service's check-then-insert
    # dedup can be raced by a concurrent identical upload; this index makes the
    # database the arbiter. FAILED invoices are excluded so re-uploading after a
    # processing failure keeps working.
    __table_args__ = (
        Index(
            "ux_invoices__tenant_checksum_active",
            "tenant_id",
            "checksum",
            unique=True,
            postgresql_where=text("status != 'failed' AND checksum IS NOT NULL"),
            sqlite_where=text("status != 'failed' AND checksum IS NOT NULL"),
        ),
    )

    # File metadata
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_size_bytes: Mapped[int | None] = mapped_column(nullable=True)
    content_type: Mapped[str] = mapped_column(String(100), default="application/pdf", nullable=False)
    checksum: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    # Status
    status: Mapped[InvoiceStatus] = mapped_column(
        db_enum(InvoiceStatus, name="invoice_status"),
        default=InvoiceStatus.UPLOADED,
        nullable=False,
        index=True,
    )
    payment_status: Mapped[PaymentStatus] = mapped_column(
        db_enum(PaymentStatus, name="payment_status"),
        default=PaymentStatus.PENDING,
        nullable=False,
    )

    # Extracted fields
    invoice_number: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    invoice_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Financial fields
    subtotal: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    cgst_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    sgst_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    igst_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    total_tax: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    total_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)

    # OCR confidence
    ocr_confidence: Mapped[float | None] = mapped_column(nullable=True)
    raw_ocr_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    extraction_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relations
    vendor_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("vendors.id", ondelete="SET NULL"), nullable=True, index=True
    )
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    vendor: Mapped["Vendor | None"] = relationship("Vendor", back_populates="invoices")
    uploaded_by_user: Mapped["User"] = relationship("User", back_populates="invoices")
    line_items: Mapped[list["InvoiceItem"]] = relationship(
        "InvoiceItem", back_populates="invoice", cascade="all, delete-orphan"
    )
    reconciliation_records: Mapped[list["ReconciliationRecord"]] = relationship(
        "ReconciliationRecord", back_populates="invoice", cascade="all, delete-orphan"
    )
    processing_jobs: Mapped[list["ProcessingJob"]] = relationship(
        "ProcessingJob", back_populates="invoice", cascade="all, delete-orphan"
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship("AuditLog", back_populates="invoice")

    def __repr__(self) -> str:
        return f"<Invoice {self.invoice_number or self.id} [{self.status}]>"
