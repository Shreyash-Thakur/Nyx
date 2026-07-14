"""normalize stored enum representation to member values

The ORM previously bound enum member *names* ('FAILED') while every migration
created the Postgres enum types with member *values* ('failed'). SQLite never
noticed (its Enum is a VARCHAR); Postgres rejected the writes outright. The
models now bind values via ``db_enum`` (values_callable), so any data written
by the old ORM binding — which can only exist on SQLite — is lowercased here.

All affected enums satisfy ``value == name.lower()`` (verified in code), so a
plain ``lower()`` is an exact mapping. On Postgres this is a no-op: the old
binding could never insert rows there.

Revision ID: 0010
Revises: 0009
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ENUM_COLUMNS: tuple[tuple[str, str], ...] = (
    ("invoices", "status"),
    ("invoices", "payment_status"),
    ("users", "role"),
    ("processing_jobs", "job_type"),
    ("processing_jobs", "status"),
    ("reconciliation_records", "status"),
    ("reconciliation_records", "discrepancy_type"),
    ("audit_logs", "event_type"),
)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return
    for table, column in _ENUM_COLUMNS:
        op.execute(f"UPDATE {table} SET {column} = lower({column}) WHERE {column} IS NOT NULL")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return
    for table, column in _ENUM_COLUMNS:
        op.execute(f"UPDATE {table} SET {column} = upper({column}) WHERE {column} IS NOT NULL")
