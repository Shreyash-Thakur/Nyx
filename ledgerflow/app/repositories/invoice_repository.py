import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models.invoice import Invoice, InvoiceStatus, PaymentStatus
from app.repositories.base import BaseRepository
from app.schemas.invoice import InvoiceFilter


class InvoiceRepository(BaseRepository[Invoice]):
    model = Invoice

    def get_with_items(self, id: uuid.UUID) -> Invoice | None:
        stmt = (
            select(Invoice)
            .options(joinedload(Invoice.line_items), joinedload(Invoice.vendor))
            .where(Invoice.id == id)
        )
        return self.db.scalar(stmt)

    def get_by_checksum(self, checksum: str) -> Invoice | None:
        stmt = select(Invoice).where(Invoice.checksum == checksum)
        return self.db.scalar(stmt)

    def find_duplicates(
        self,
        invoice_number: str,
        vendor_id: uuid.UUID,
        invoice_date: date,
        window_days: int = 30,
    ) -> list[Invoice]:
        from datetime import timedelta

        date_min = invoice_date - timedelta(days=window_days)
        date_max = invoice_date + timedelta(days=window_days)
        stmt = (
            select(Invoice)
            .where(
                and_(
                    Invoice.invoice_number == invoice_number,
                    Invoice.vendor_id == vendor_id,
                    Invoice.invoice_date.between(date_min, date_max),
                    Invoice.status != InvoiceStatus.FAILED,
                )
            )
        )
        return list(self.db.scalars(stmt).all())

    def filter_paginated(
        self,
        filters: InvoiceFilter,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Invoice], int]:
        conditions = []

        if filters.status:
            conditions.append(Invoice.status == filters.status)
        if filters.payment_status:
            conditions.append(Invoice.payment_status == filters.payment_status)
        if filters.vendor_id:
            conditions.append(Invoice.vendor_id == filters.vendor_id)
        if filters.invoice_number:
            conditions.append(Invoice.invoice_number.ilike(f"%{filters.invoice_number}%"))
        if filters.date_from:
            conditions.append(Invoice.invoice_date >= filters.date_from)
        if filters.date_to:
            conditions.append(Invoice.invoice_date <= filters.date_to)
        if filters.amount_min is not None:
            conditions.append(Invoice.total_amount >= filters.amount_min)
        if filters.amount_max is not None:
            conditions.append(Invoice.total_amount <= filters.amount_max)
        if filters.search:
            pattern = f"%{filters.search}%"
            conditions.append(
                or_(
                    Invoice.invoice_number.ilike(pattern),
                    Invoice.original_filename.ilike(pattern),
                )
            )

        where_clause = and_(*conditions) if conditions else True

        total_stmt = select(func.count()).select_from(Invoice).where(where_clause)
        total = self.db.scalar(total_stmt) or 0

        stmt = (
            select(Invoice)
            .options(joinedload(Invoice.vendor))
            .where(where_clause)
            .order_by(Invoice.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.scalars(stmt).unique().all()), total

    def count_by_status(self) -> dict[str, int]:
        stmt = (
            select(Invoice.status, func.count().label("cnt"))
            .group_by(Invoice.status)
        )
        rows = self.db.execute(stmt).all()
        return {row.status.value: row.cnt for row in rows}

    def total_amount_by_payment_status(self, payment_status: PaymentStatus) -> Decimal:
        stmt = (
            select(func.coalesce(func.sum(Invoice.total_amount), 0))
            .where(Invoice.payment_status == payment_status)
        )
        return self.db.scalar(stmt) or Decimal("0")
