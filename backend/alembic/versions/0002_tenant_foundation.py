"""tenant foundation (ADR-0008)

Adds the ``tenants`` table, seeds a single default tenant, and adds a
``tenant_id`` column to every tenant-scoped domain table. Existing rows are
backfilled to the default tenant via the column server default.

Portable across SQLite and PostgreSQL:
* ``tenant_id`` is a plain indexed GUID with no DB-level foreign key (tenant
  integrity is enforced at the application layer, ADR-0004), so adding it is a
  simple ``ADD COLUMN ... NOT NULL DEFAULT`` that works on both engines.
* the default tenant is inserted with ``bulk_insert`` so booleans/UUIDs render
  correctly per dialect.

Revision ID: 0002
Revises: 0001
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.core.db_types import GUID
from app.core.tenancy import DEFAULT_TENANT_ID, DEFAULT_TENANT_SLUG

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TENANT_SCOPED_TABLES = (
    "users",
    "vendors",
    "invoices",
    "invoice_items",
    "reconciliation_records",
    "processing_jobs",
    "audit_logs",
)


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_tenants_slug", "tenants", ["slug"], unique=True)

    tenants = sa.table(
        "tenants",
        sa.column("id", GUID()),
        sa.column("name", sa.String),
        sa.column("slug", sa.String),
        sa.column("is_active", sa.Boolean),
    )
    op.bulk_insert(
        tenants,
        [{
            "id": DEFAULT_TENANT_ID,
            "name": "Default Tenant",
            "slug": DEFAULT_TENANT_SLUG,
            "is_active": True,
        }],
    )

    default = f"'{DEFAULT_TENANT_ID}'"
    for table in _TENANT_SCOPED_TABLES:
        op.add_column(
            table,
            sa.Column(
                "tenant_id",
                GUID(),
                nullable=False,
                server_default=sa.text(default),
            ),
        )
        op.create_index(f"ix_{table}_tenant_id", table, ["tenant_id"])


def downgrade() -> None:
    for table in _TENANT_SCOPED_TABLES:
        op.drop_index(f"ix_{table}_tenant_id", table_name=table)
        op.drop_column(table, "tenant_id")
    op.drop_index("ix_tenants_slug", table_name="tenants")
    op.drop_table("tenants")
