from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.invoice import InvoiceStatus, PaymentStatus


class InvoiceItemResponse(BaseModel):
    id: UUID
    description: str
    hsn_sac_code: str | None
    quantity: Decimal | None
    unit: str | None
    unit_price: Decimal | None
    discount_amount: Decimal | None
    tax_rate: Decimal | None
    tax_amount: Decimal | None
    line_total: Decimal | None
    sequence_number: int

    model_config = ConfigDict(from_attributes=True)


class InvoiceResponse(BaseModel):
    id: UUID
    original_filename: str
    status: InvoiceStatus
    payment_status: PaymentStatus

    invoice_number: str | None
    invoice_date: date | None
    due_date: date | None

    vendor_id: UUID | None
    vendor_name: str | None = None

    subtotal: Decimal | None
    cgst_amount: Decimal | None
    sgst_amount: Decimal | None
    igst_amount: Decimal | None
    total_tax: Decimal | None
    total_amount: Decimal | None
    currency: str

    ocr_confidence: float | None
    extraction_notes: str | None

    uploaded_by: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InvoiceDetailResponse(InvoiceResponse):
    line_items: list[InvoiceItemResponse] = []
    file_size_bytes: int | None
    checksum: str | None


class InvoiceUpdate(BaseModel):
    invoice_number: str | None = None
    invoice_date: date | None = None
    due_date: date | None = None
    vendor_id: UUID | None = None
    payment_status: PaymentStatus | None = None
    subtotal: Decimal | None = None
    cgst_amount: Decimal | None = None
    sgst_amount: Decimal | None = None
    igst_amount: Decimal | None = None
    total_tax: Decimal | None = None
    total_amount: Decimal | None = None


class InvoiceFilter(BaseModel):
    status: InvoiceStatus | None = None
    payment_status: PaymentStatus | None = None
    vendor_id: UUID | None = None
    invoice_number: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    amount_min: Decimal | None = None
    amount_max: Decimal | None = None
    search: str | None = None


class JobStatusResponse(BaseModel):
    job_id: UUID
    invoice_id: UUID
    job_type: str
    status: str
    attempt_count: int
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None

    model_config = ConfigDict(from_attributes=True)
