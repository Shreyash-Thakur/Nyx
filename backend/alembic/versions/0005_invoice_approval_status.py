"""finance approval gate: new invoice/audit enum values

Adds PENDING_APPROVAL and REJECTED to invoice_status, and three new audit
event types for the approval flow. On Postgres these are native enum types
and require ALTER TYPE ... ADD VALUE; on SQLite the Enum is inlined as a
VARCHAR (no separate type object), so there is nothing to migrate there.

Revision ID: 0005
Revises: 0004
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_INVOICE_STATUS_VALUES = ("pending_approval", "approved", "rejected")
_NEW_AUDIT_EVENT_TYPES = (
    "invoice_approval_required",
    "invoice_approved",
    "invoice_rejected",
    "invoice_tally_export_generated",
)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    # ALTER TYPE ... ADD VALUE cannot run inside the transaction Alembic wraps
    # migrations in by default; each statement needs its own autocommit block.
    for value in _NEW_INVOICE_STATUS_VALUES:
        with op.get_context().autocommit_block():
            op.execute(f"ALTER TYPE invoice_status ADD VALUE IF NOT EXISTS '{value}'")
    for value in _NEW_AUDIT_EVENT_TYPES:
        with op.get_context().autocommit_block():
            op.execute(f"ALTER TYPE audit_event_type ADD VALUE IF NOT EXISTS '{value}'")


def downgrade() -> None:
    # Postgres has no ALTER TYPE ... DROP VALUE; a real downgrade would need to
    # rebuild the enum type and every column using it. Not worth it for an
    # additive, backward-compatible change -- downgrading this migration is a
    # no-op, matching the values simply going unused.
    pass
