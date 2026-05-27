import uuid
from datetime import datetime

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.models.audit_log import AuditEventType, AuditLog
from app.repositories.base import BaseRepository


class AuditRepository(BaseRepository[AuditLog]):
    model = AuditLog

    def log(
        self,
        event_type: AuditEventType,
        description: str,
        *,
        user_id: uuid.UUID | None = None,
        invoice_id: uuid.UUID | None = None,
        metadata: dict | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuditLog:
        entry = AuditLog(
            event_type=event_type,
            description=description,
            user_id=user_id,
            invoice_id=invoice_id,
            metadata=metadata,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return self.save(entry)

    def get_for_invoice(self, invoice_id: uuid.UUID, *, limit: int = 50) -> list[AuditLog]:
        stmt = (
            select(AuditLog)
            .where(AuditLog.invoice_id == invoice_id)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )
        return list(self.db.scalars(stmt).all())

    def get_for_user(self, user_id: uuid.UUID, *, limit: int = 100) -> list[AuditLog]:
        stmt = (
            select(AuditLog)
            .where(AuditLog.user_id == user_id)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )
        return list(self.db.scalars(stmt).all())

    def list_paginated(
        self,
        *,
        user_id: uuid.UUID | None = None,
        invoice_id: uuid.UUID | None = None,
        event_type: AuditEventType | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[AuditLog], int]:
        from sqlalchemy import func

        conditions = []
        if user_id:
            conditions.append(AuditLog.user_id == user_id)
        if invoice_id:
            conditions.append(AuditLog.invoice_id == invoice_id)
        if event_type:
            conditions.append(AuditLog.event_type == event_type)
        if date_from:
            conditions.append(AuditLog.created_at >= date_from)
        if date_to:
            conditions.append(AuditLog.created_at <= date_to)

        where_clause = and_(*conditions) if conditions else True
        total = self.db.scalar(
            select(func.count()).select_from(AuditLog).where(where_clause)
        ) or 0
        stmt = (
            select(AuditLog)
            .where(where_clause)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.scalars(stmt).all()), total
