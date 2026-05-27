from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.vendor import Vendor
from app.repositories.base import BaseRepository


class VendorRepository(BaseRepository[Vendor]):
    model = Vendor

    def get_by_gst(self, gst_number: str) -> Vendor | None:
        stmt = select(Vendor).where(Vendor.gst_number == gst_number.upper())
        return self.db.scalar(stmt)

    def find_by_name(self, name: str) -> Vendor | None:
        normalized = name.strip().lower()
        stmt = select(Vendor).where(Vendor.normalized_name == normalized)
        return self.db.scalar(stmt)

    def search(self, query: str, *, limit: int = 20, offset: int = 0) -> tuple[list[Vendor], int]:
        pattern = f"%{query.lower()}%"
        base_filter = or_(
            func.lower(Vendor.name).like(pattern),
            Vendor.gst_number.ilike(pattern),
        )
        total = self.count(base_filter)
        stmt = select(Vendor).where(base_filter).limit(limit).offset(offset)
        return list(self.db.scalars(stmt).all()), total

    def list_active(self, *, limit: int = 50, offset: int = 0) -> tuple[list[Vendor], int]:
        total = self.count(Vendor.is_active.is_(True))
        stmt = (
            select(Vendor)
            .where(Vendor.is_active.is_(True))
            .order_by(Vendor.name)
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.scalars(stmt).all()), total
