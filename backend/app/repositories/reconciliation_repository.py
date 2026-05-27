import uuid
from decimal import Decimal

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session, joinedload

from app.models.reconciliation import DiscrepancyType, ReconciliationRecord, ReconciliationStatus
from app.repositories.base import BaseRepository
from app.schemas.reconciliation import ReconciliationFilter


class ReconciliationRepository(BaseRepository[ReconciliationRecord]):
    model = ReconciliationRecord

    def get_by_invoice(self, invoice_id: uuid.UUID) -> list[ReconciliationRecord]:
        stmt = (
            select(ReconciliationRecord)
            .where(ReconciliationRecord.invoice_id == invoice_id)
            .order_by(ReconciliationRecord.created_at.desc())
        )
        return list(self.db.scalars(stmt).all())

    def filter_paginated(
        self,
        filters: ReconciliationFilter,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[ReconciliationRecord], int]:
        conditions = []

        if filters.status:
            conditions.append(ReconciliationRecord.status == filters.status)
        if filters.discrepancy_type:
            conditions.append(ReconciliationRecord.discrepancy_type == filters.discrepancy_type)
        if filters.date_from:
            conditions.append(ReconciliationRecord.created_at >= filters.date_from)
        if filters.date_to:
            conditions.append(ReconciliationRecord.created_at <= filters.date_to)

        where_clause = and_(*conditions) if conditions else True

        total = self.db.scalar(
            select(func.count()).select_from(ReconciliationRecord).where(where_clause)
        ) or 0

        stmt = (
            select(ReconciliationRecord)
            .where(where_clause)
            .order_by(ReconciliationRecord.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.scalars(stmt).all()), total

    def discrepancy_summary(self) -> dict:
        total_stmt = select(func.count()).select_from(ReconciliationRecord).where(
            ReconciliationRecord.discrepancy_type.isnot(None)
        )
        total = self.db.scalar(total_stmt) or 0

        unresolved_stmt = select(func.count()).select_from(ReconciliationRecord).where(
            and_(
                ReconciliationRecord.discrepancy_type.isnot(None),
                ReconciliationRecord.status.notin_(
                    [ReconciliationStatus.MATCHED, ReconciliationStatus.MANUALLY_RESOLVED]
                ),
            )
        )
        unresolved = self.db.scalar(unresolved_stmt) or 0

        amount_stmt = select(
            func.coalesce(func.sum(ReconciliationRecord.discrepancy_amount), 0)
        ).where(ReconciliationRecord.discrepancy_amount.isnot(None))
        total_amount = self.db.scalar(amount_stmt) or Decimal("0")

        by_type_stmt = (
            select(ReconciliationRecord.discrepancy_type, func.count().label("cnt"))
            .where(ReconciliationRecord.discrepancy_type.isnot(None))
            .group_by(ReconciliationRecord.discrepancy_type)
        )
        by_type = {
            row.discrepancy_type.value: row.cnt
            for row in self.db.execute(by_type_stmt).all()
        }

        return {
            "total_discrepancies": total,
            "unresolved": unresolved,
            "resolved": total - unresolved,
            "total_discrepancy_amount": total_amount,
            "by_type": by_type,
        }
