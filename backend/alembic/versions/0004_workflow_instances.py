"""workflow instances (ADR-0003)

Durable record of workflow runs for the right-sized workflow engine.

Revision ID: 0004
Revises: 0003
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.core.db_types import GUID

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workflow_instances",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("tenant_id", GUID(), nullable=False),
        sa.Column("workflow_name", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="running"),
        sa.Column("current_step", sa.String(100), nullable=True),
        sa.Column("context", sa.JSON, nullable=True),
        sa.Column("actor_id", GUID(), nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_workflow_instances_tenant_id", "workflow_instances", ["tenant_id"])
    op.create_index("ix_workflow_instances_workflow_name", "workflow_instances", ["workflow_name"])
    op.create_index("ix_workflow_instances_status", "workflow_instances", ["status"])


def downgrade() -> None:
    op.drop_index("ix_workflow_instances_status", table_name="workflow_instances")
    op.drop_index("ix_workflow_instances_workflow_name", table_name="workflow_instances")
    op.drop_index("ix_workflow_instances_tenant_id", table_name="workflow_instances")
    op.drop_table("workflow_instances")
