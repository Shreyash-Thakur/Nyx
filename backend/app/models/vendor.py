from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel
from app.models.tenant import TenantMixin

if TYPE_CHECKING:
    from app.models.invoice import Invoice


class Vendor(TenantMixin, BaseModel):
    __tablename__ = "vendors"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    gst_number: Mapped[str | None] = mapped_column(String(20), unique=True, nullable=True, index=True)
    pan_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    invoices: Mapped[list["Invoice"]] = relationship("Invoice", back_populates="vendor")

    def __repr__(self) -> str:
        return f"<Vendor {self.name}>"
