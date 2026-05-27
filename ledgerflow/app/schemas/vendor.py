from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator


class VendorCreate(BaseModel):
    name: str
    gst_number: str | None = None
    pan_number: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    address: str | None = None

    @field_validator("gst_number")
    @classmethod
    def validate_gst(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.upper().strip()
        if len(v) != 15:
            raise ValueError("GST number must be 15 characters")
        return v


class VendorUpdate(BaseModel):
    name: str | None = None
    gst_number: str | None = None
    pan_number: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    address: str | None = None
    is_active: bool | None = None


class VendorResponse(BaseModel):
    id: UUID
    name: str
    gst_number: str | None
    pan_number: str | None
    email: str | None
    phone: str | None
    address: str | None
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class VendorSummary(BaseModel):
    id: UUID
    name: str
    gst_number: str | None

    model_config = ConfigDict(from_attributes=True)
