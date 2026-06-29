"""durable event log (ADR-0002)

Append-only ``events`` table that backs the in-process event bus and is the
source of truth for future async relays / replay.

Revision ID: 0003
Revises: 0002
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.core.db_types import GUID

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "events",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("tenant_id", GUID(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("aggregate_type", sa.String(50), nullable=True),
        sa.Column("aggregate_id", GUID(), nullable=True),
        sa.Column("actor_id", GUID(), nullable=True),
        sa.Column("payload", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_events_tenant_id", "events", ["tenant_id"])
    op.create_index("ix_events_name", "events", ["name"])
    op.create_index("ix_events_aggregate_id", "events", ["aggregate_id"])
    op.create_index("ix_events_created_at", "events", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_events_created_at", table_name="events")
    op.drop_index("ix_events_aggregate_id", table_name="events")
    op.drop_index("ix_events_name", table_name="events")
    op.drop_index("ix_events_tenant_id", table_name="events")
    op.drop_table("events")
