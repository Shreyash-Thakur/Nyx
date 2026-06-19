"""initial schema

Revision ID: 0001
Revises:
Create Date: 2025-05-27 00:00:00.000000

Notes
-----
This migration is intentionally portable across PostgreSQL and SQLite.

* UUIDs use ``app.core.db_types.GUID`` — native UUID on Postgres, CHAR(36)
  elsewhere.
* JSON columns use ``sa.JSON`` (renders as JSONB on Postgres, JSON on SQLite).
* Enums use ``sa.Enum`` with no ``create_type`` override — SQLAlchemy emits
  the native CREATE TYPE on Postgres and a VARCHAR + CHECK on SQLite.
* ``updated_at`` is maintained by the SQLAlchemy ``onupdate=func.now()``
  on the ORM mixin (see app/models/base.py); we no longer install a
  Postgres-specific PL/pgSQL trigger here.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.core.db_types import GUID

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # users
    op.create_table(
        "users",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column(
            "role",
            sa.Enum("admin", "accountant", "viewer", name="user_role"),
            nullable=False,
            server_default="accountant",
        ),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("1")),
        sa.Column("is_verified", sa.Boolean, nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # vendors
    op.create_table(
        "vendors",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("normalized_name", sa.String(255), nullable=False),
        sa.Column("gst_number", sa.String(20), nullable=True),
        sa.Column("pan_number", sa.String(20), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("address", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_vendors_name", "vendors", ["name"])
    op.create_index("ix_vendors_gst_number", "vendors", ["gst_number"], unique=True)

    # invoices
    op.create_table(
        "invoices",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("original_filename", sa.String(500), nullable=False),
        sa.Column("storage_path", sa.String(1000), nullable=False),
        sa.Column("file_size_bytes", sa.Integer, nullable=True),
        sa.Column("content_type", sa.String(100), nullable=False, server_default="application/pdf"),
        sa.Column("checksum", sa.String(64), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "uploaded", "queued", "processing", "extracted",
                "validated", "reconciled", "failed", "duplicate",
                name="invoice_status",
            ),
            nullable=False,
            server_default="uploaded",
        ),
        sa.Column(
            "payment_status",
            sa.Enum(
                "pending", "paid", "overdue", "partial", "cancelled",
                name="payment_status",
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("invoice_number", sa.String(100), nullable=True),
        sa.Column("invoice_date", sa.Date, nullable=True),
        sa.Column("due_date", sa.Date, nullable=True),
        sa.Column("subtotal", sa.Numeric(14, 2), nullable=True),
        sa.Column("cgst_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("sgst_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("igst_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("total_tax", sa.Numeric(14, 2), nullable=True),
        sa.Column("total_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("ocr_confidence", sa.Float, nullable=True),
        sa.Column("raw_ocr_text", sa.Text, nullable=True),
        sa.Column("extraction_notes", sa.Text, nullable=True),
        sa.Column("vendor_id", GUID(), sa.ForeignKey("vendors.id", ondelete="SET NULL"), nullable=True),
        sa.Column("uploaded_by", GUID(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_invoices_status", "invoices", ["status"])
    op.create_index("ix_invoices_invoice_number", "invoices", ["invoice_number"])
    op.create_index("ix_invoices_invoice_date", "invoices", ["invoice_date"])
    op.create_index("ix_invoices_checksum", "invoices", ["checksum"])
    op.create_index("ix_invoices_vendor_id", "invoices", ["vendor_id"])

    # invoice_items
    op.create_table(
        "invoice_items",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("invoice_id", GUID(), sa.ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("hsn_sac_code", sa.String(20), nullable=True),
        sa.Column("quantity", sa.Numeric(10, 3), nullable=True),
        sa.Column("unit", sa.String(50), nullable=True),
        sa.Column("unit_price", sa.Numeric(14, 2), nullable=True),
        sa.Column("discount_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("tax_rate", sa.Numeric(5, 2), nullable=True),
        sa.Column("tax_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("line_total", sa.Numeric(14, 2), nullable=True),
        sa.Column("sequence_number", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_invoice_items_invoice_id", "invoice_items", ["invoice_id"])

    # reconciliation_records
    op.create_table(
        "reconciliation_records",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("invoice_id", GUID(), sa.ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("matched_by", GUID(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "pending", "matched", "partial_match", "unmatched",
                "discrepancy", "duplicate", "manually_resolved",
                name="reconciliation_status",
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "discrepancy_type",
            sa.Enum(
                "amount_mismatch", "duplicate_invoice", "vendor_mismatch",
                "date_mismatch", "missing_reference", "tax_mismatch",
                name="discrepancy_type",
            ),
            nullable=True,
        ),
        sa.Column("confidence_score", sa.Float, nullable=True),
        sa.Column("reference_document_id", sa.String(200), nullable=True),
        sa.Column("reference_document_type", sa.String(50), nullable=True),
        sa.Column("expected_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("actual_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("discrepancy_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("tolerance_applied", sa.Numeric(14, 2), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("resolution_notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_recon_invoice_id", "reconciliation_records", ["invoice_id"])
    op.create_index("ix_recon_status", "reconciliation_records", ["status"])

    # processing_jobs
    op.create_table(
        "processing_jobs",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("invoice_id", GUID(), sa.ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "job_type",
            sa.Enum("ocr_extraction", "data_validation", "reconciliation", name="job_type"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "queued", "started", "completed", "failed", "retrying", "cancelled",
                name="job_status",
            ),
            nullable=False,
            server_default="queued",
        ),
        sa.Column("rq_job_id", sa.String(200), nullable=True),
        sa.Column("attempt_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer, nullable=False, server_default="3"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result", sa.JSON, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("error_traceback", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_jobs_invoice_id", "processing_jobs", ["invoice_id"])
    op.create_index("ix_jobs_status", "processing_jobs", ["status"])
    op.create_index("ix_jobs_rq_job_id", "processing_jobs", ["rq_job_id"], unique=True)

    # audit_logs
    op.create_table(
        "audit_logs",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "event_type",
            sa.Enum(
                "user_login", "user_logout", "user_created", "password_changed",
                "invoice_uploaded", "invoice_queued", "invoice_processing_started",
                "invoice_processing_completed", "invoice_processing_failed",
                "invoice_validated", "invoice_updated", "invoice_deleted",
                "invoice_duplicate_detected",
                "reconciliation_started", "reconciliation_matched",
                "reconciliation_discrepancy", "reconciliation_resolved",
                "vendor_created", "vendor_updated",
                name="audit_event_type",
            ),
            nullable=False,
        ),
        sa.Column("user_id", GUID(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("invoice_id", GUID(), sa.ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("extra_data", sa.JSON, nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_audit_event_type", "audit_logs", ["event_type"])
    op.create_index("ix_audit_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_invoice_id", "audit_logs", ["invoice_id"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("processing_jobs")
    op.drop_table("reconciliation_records")
    op.drop_table("invoice_items")
    op.drop_table("invoices")
    op.drop_table("vendors")
    op.drop_table("users")

    # On Postgres the Enum types persist as separate objects and must be dropped
    # explicitly. On SQLite enums are inlined CHECK constraints — nothing to do.
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for enum_name in (
            "audit_event_type", "job_status", "job_type",
            "discrepancy_type", "reconciliation_status",
            "payment_status", "invoice_status", "user_role",
        ):
            op.execute(f"DROP TYPE IF EXISTS {enum_name}")
