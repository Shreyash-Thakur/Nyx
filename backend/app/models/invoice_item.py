import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db_types import GUID
from app.models.base import BaseModel
from app.models.tenant import TenantMixin

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.invoice import Invoice


class InvoiceItem(TenantMixin, BaseModel):
    __tablename__ = "invoice_items"

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("invoices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    description: Mapped[str] = mapped_column(Text, nullable=False)
    hsn_sac_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    discount_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    tax_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    tax_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    line_total: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    sequence_number: Mapped[int] = mapped_column(default=0, nullable=False)

    invoice: Mapped["Invoice"] = relationship("Invoice", back_populates="line_items")

    def __repr__(self) -> str:
        return f"<InvoiceItem {self.description[:30]} – {self.line_total}>"
