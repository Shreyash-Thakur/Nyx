"""Cross-database column types.

Lets the same models work on PostgreSQL (production) and SQLite (local dev)
without per-dialect branching in every model file.
"""
from __future__ import annotations

import uuid

from sqlalchemy import CHAR
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.types import TypeDecorator


class GUID(TypeDecorator):
    """Platform-independent UUID column.

    On PostgreSQL: uses the native ``UUID`` type.
    Everywhere else (SQLite, MySQL): stores as ``CHAR(36)`` strings.
    Always returns ``uuid.UUID`` instances to Python code.
    """

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            # The PG UUID adapter handles uuid.UUID natively.
            return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
        # SQLite / others: store canonical string form.
        if isinstance(value, uuid.UUID):
            return str(value)
        return str(uuid.UUID(str(value)))

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(str(value))
