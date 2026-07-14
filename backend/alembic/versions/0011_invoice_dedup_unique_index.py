"""race-safe duplicate-upload guard (SEC-4)

The upload path's check-then-insert dedup can be raced by a concurrent
identical upload (TD-12). This partial unique index makes the database the
arbiter: one active (non-FAILED) invoice per (tenant, checksum). FAILED
invoices are excluded so re-uploading after a processing failure keeps
working — the exact reason a plain unique constraint was avoided originally.

Revision ID: 0011
Revises: 0010
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_INDEX = "ux_invoices__tenant_checksum_active"
_WHERE = "status != 'failed' AND checksum IS NOT NULL"


def upgrade() -> None:
    # `postgresql_where`/`sqlite_where` want a SQL expression element, not a raw
    # str — a bare string trips the compiler ('str' has no _compiler_dispatch).
    where = sa.text(_WHERE)
    op.create_index(
        _INDEX,
        "invoices",
        ["tenant_id", "checksum"],
        unique=True,
        postgresql_where=where,
        sqlite_where=where,
    )


def downgrade() -> None:
    op.drop_index(_INDEX, table_name="invoices")
