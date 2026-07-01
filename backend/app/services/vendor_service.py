import uuid

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError
from app.models.audit_log import AuditEventType
from app.models.user import User
from app.models.vendor import Vendor
from app.repositories.audit_repository import AuditRepository
from app.repositories.vendor_repository import VendorRepository
from app.schemas.vendor import VendorCreate, VendorUpdate


class VendorService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.vendor_repo = VendorRepository(db)
        self.audit_repo = AuditRepository(db)

    def create(self, payload: VendorCreate, current_user: User) -> Vendor:
        if payload.gst_number:
            existing = self.vendor_repo.get_by_gst(payload.gst_number, current_user.tenant_id)
            if existing:
                raise ConflictError(f"Vendor with GST {payload.gst_number} already exists")

        vendor = Vendor(
            tenant_id=current_user.tenant_id,
            name=payload.name,
            normalized_name=payload.name.strip().lower(),
            gst_number=payload.gst_number,
            pan_number=payload.pan_number,
            email=payload.email,
            phone=payload.phone,
            address=payload.address,
        )
        vendor = self.vendor_repo.save(vendor)
        self.audit_repo.log(
            AuditEventType.VENDOR_CREATED,
            f"Vendor created: {vendor.name}",
            tenant_id=vendor.tenant_id,
            user_id=current_user.id,
            extra_data={"vendor_id": str(vendor.id)},
        )
        self.db.commit()
        return vendor

    def get(self, vendor_id: uuid.UUID, tenant_id: uuid.UUID) -> Vendor:
        return self.vendor_repo.get_for_tenant_or_raise(vendor_id, tenant_id)

    def update(self, vendor_id: uuid.UUID, payload: VendorUpdate, current_user: User) -> Vendor:
        vendor = self.get(vendor_id, current_user.tenant_id)

        for field_name, value in payload.model_dump(exclude_none=True).items():
            setattr(vendor, field_name, value)

        if payload.name:
            vendor.normalized_name = payload.name.strip().lower()

        vendor = self.vendor_repo.save(vendor)
        self.audit_repo.log(
            AuditEventType.VENDOR_UPDATED,
            f"Vendor updated: {vendor.name}",
            tenant_id=vendor.tenant_id,
            user_id=current_user.id,
            extra_data={"vendor_id": str(vendor.id)},
        )
        self.db.commit()
        return vendor

    def list(
        self,
        tenant_id: uuid.UUID,
        search: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Vendor], int]:
        offset = (page - 1) * page_size
        if search:
            return self.vendor_repo.search(search, tenant_id, limit=page_size, offset=offset)
        return self.vendor_repo.list_active(tenant_id, limit=page_size, offset=offset)
