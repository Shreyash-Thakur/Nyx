import uuid

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.vendor import Vendor
from app.repositories.base import BaseRepository


class VendorRepository(BaseRepository[Vendor]):
    model = Vendor

    def get_for_tenant(self, id: uuid.UUID, tenant_id: uuid.UUID) -> Vendor | None:
        stmt = select(Vendor).where(Vendor.id == id, Vendor.tenant_id == tenant_id)
        return self.db.scalar(stmt)

    def get_for_tenant_or_raise(self, id: uuid.UUID, tenant_id: uuid.UUID) -> Vendor:
        vendor = self.get_for_tenant(id, tenant_id)
        if vendor is None:
            raise NotFoundError("Vendor", str(id))
        return vendor

    def get_by_gst(self, gst_number: str, tenant_id: uuid.UUID) -> Vendor | None:
        stmt = select(Vendor).where(
            Vendor.gst_number == gst_number.upper(), Vendor.tenant_id == tenant_id
        )
        return self.db.scalar(stmt)

    def find_by_name(self, name: str, tenant_id: uuid.UUID) -> Vendor | None:
        normalized = name.strip().lower()
        stmt = select(Vendor).where(
            Vendor.normalized_name == normalized, Vendor.tenant_id == tenant_id
        )
        return self.db.scalar(stmt)

    def search(
        self, query: str, tenant_id, *, limit: int = 20, offset: int = 0
    ) -> tuple[list[Vendor], int]:
        pattern = f"%{query.lower()}%"
        base_filter = and_(
            Vendor.tenant_id == tenant_id,
            or_(
                func.lower(Vendor.name).like(pattern),
                Vendor.gst_number.ilike(pattern),
            ),
        )
        total = self.count(base_filter)
        stmt = select(Vendor).where(base_filter).limit(limit).offset(offset)
        return list(self.db.scalars(stmt).all()), total

    def list_active(self, tenant_id, *, limit: int = 50, offset: int = 0) -> tuple[list[Vendor], int]:
        base_filter = and_(Vendor.tenant_id == tenant_id, Vendor.is_active.is_(True))
        total = self.count(base_filter)
        stmt = (
            select(Vendor)
            .where(base_filter)
            .order_by(Vendor.name)
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.scalars(stmt).all()), total
