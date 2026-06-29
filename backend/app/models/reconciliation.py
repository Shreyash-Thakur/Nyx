import enum
import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db_types import GUID
from app.models.base import BaseModel
from app.models.tenant import TenantMixin

if TYPE_CHECKING:
    from app.models.invoice import Invoice
    from app.models.user import User


class ReconciliationStatus(str, enum.Enum):
    PENDING = "pending"
    MATCHED = "matched"
    PARTIAL_MATCH = "partial_match"
    UNMATCHED = "unmatched"
    DISCREPANCY = "discrepancy"
    DUPLICATE = "duplicate"
    MANUALLY_RESOLVED = "manually_resolved"


class DiscrepancyType(str, enum.Enum):
    AMOUNT_MISMATCH = "amount_mismatch"
    DUPLICATE_INVOICE = "duplicate_invoice"
    VENDOR_MISMATCH = "vendor_mismatch"
    DATE_MISMATCH = "date_mismatch"
    MISSING_REFERENCE = "missing_reference"
    TAX_MISMATCH = "tax_mismatch"


class ReconciliationRecord(TenantMixin, BaseModel):
    __tablename__ = "reconciliation_records"

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("invoices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    matched_by: Mapped[uuid.UUID | None] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    status: Mapped[ReconciliationStatus] = mapped_column(
        Enum(ReconciliationStatus, name="reconciliation_status"),
        default=ReconciliationStatus.PENDING,
        nullable=False,
        index=True,
    )
    discrepancy_type: Mapped[DiscrepancyType | None] = mapped_column(
        Enum(DiscrepancyType, name="discrepancy_type"),
        nullable=True,
    )

    # Matching details
    confidence_score: Mapped[float | None] = mapped_column(nullable=True)
    reference_document_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    reference_document_type: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Financial discrepancy
    expected_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    actual_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    discrepancy_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    tolerance_applied: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    invoice: Mapped["Invoice"] = relationship("Invoice", back_populates="reconciliation_records")
    matched_by_user: Mapped["User | None"] = relationship("User")

    def __repr__(self) -> str:
        return f"<ReconciliationRecord {self.invoice_id} [{self.status}]>"
