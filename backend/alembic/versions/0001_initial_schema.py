"""initial schema

Revision ID: 0001
Revises:
Create Date: 2025-05-27 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enums
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE user_role AS ENUM ('admin', 'accountant', 'viewer');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE invoice_status AS ENUM
                ('uploaded','queued','processing','extracted','validated','reconciled','failed','duplicate');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE payment_status AS ENUM ('pending','paid','overdue','partial','cancelled');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE reconciliation_status AS ENUM
                ('pending','matched','partial_match','unmatched','discrepancy','duplicate','manually_resolved');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE discrepancy_type AS ENUM
                ('amount_mismatch','duplicate_invoice','vendor_mismatch','date_mismatch','missing_reference','tax_mismatch');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE job_type AS ENUM ('ocr_extraction','data_validation','reconciliation');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE job_status AS ENUM ('queued','started','completed','failed','retrying','cancelled');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE audit_event_type AS ENUM (
                'user_login','user_logout','user_created','password_changed',
                'invoice_uploaded','invoice_queued','invoice_processing_started',
                'invoice_processing_completed','invoice_processing_failed',
                'invoice_validated','invoice_updated','invoice_deleted','invoice_duplicate_detected',
                'reconciliation_started','reconciliation_matched','reconciliation_discrepancy','reconciliation_resolved',
                'vendor_created','vendor_updated');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)

    # users
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("role", sa.Enum("admin", "accountant", "viewer", name="user_role", create_type=False), nullable=False, server_default="accountant"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("is_verified", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # vendors
    op.create_table(
        "vendors",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("normalized_name", sa.String(255), nullable=False),
        sa.Column("gst_number", sa.String(20), nullable=True),
        sa.Column("pan_number", sa.String(20), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("address", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_vendors_name", "vendors", ["name"])
    op.create_index("ix_vendors_gst_number", "vendors", ["gst_number"], unique=True)

    # invoices
    op.create_table(
        "invoices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("original_filename", sa.String(500), nullable=False),
        sa.Column("storage_path", sa.String(1000), nullable=False),
        sa.Column("file_size_bytes", sa.Integer, nullable=True),
        sa.Column("content_type", sa.String(100), nullable=False, server_default="application/pdf"),
        sa.Column("checksum", sa.String(64), nullable=True),
        sa.Column("status", sa.Enum(name="invoice_status", create_type=False), nullable=False, server_default="uploaded"),
        sa.Column("payment_status", sa.Enum(name="payment_status", create_type=False), nullable=False, server_default="pending"),
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
        sa.Column("vendor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vendors.id", ondelete="SET NULL"), nullable=True),
        sa.Column("uploaded_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
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
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False),
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
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("matched_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.Enum(name="reconciliation_status", create_type=False), nullable=False, server_default="pending"),
        sa.Column("discrepancy_type", sa.Enum(name="discrepancy_type", create_type=False), nullable=True),
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
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_type", sa.Enum(name="job_type", create_type=False), nullable=False),
        sa.Column("status", sa.Enum(name="job_status", create_type=False), nullable=False, server_default="queued"),
        sa.Column("rq_job_id", sa.String(200), nullable=True),
        sa.Column("attempt_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer, nullable=False, server_default="3"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result", postgresql.JSONB, nullable=True),
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
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_type", sa.Enum(name="audit_event_type", create_type=False), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("extra_data", postgresql.JSONB, nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_audit_event_type", "audit_logs", ["event_type"])
    op.create_index("ix_audit_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_invoice_id", "audit_logs", ["invoice_id"])

    # updated_at trigger function
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ language 'plpgsql';
    """)

    for tbl in ["users", "vendors", "invoices", "invoice_items",
                "reconciliation_records", "processing_jobs", "audit_logs"]:
        op.execute(f"""
            CREATE TRIGGER set_updated_at
            BEFORE UPDATE ON {tbl}
            FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();
        """)


def downgrade() -> None:
    for tbl in ["audit_logs", "processing_jobs", "reconciliation_records",
                "invoice_items", "invoices", "vendors", "users"]:
        op.execute(f"DROP TRIGGER IF EXISTS set_updated_at ON {tbl}")
        op.drop_table(tbl)

    for enum in [
        "audit_event_type", "job_status", "job_type",
        "discrepancy_type", "reconciliation_status",
        "payment_status", "invoice_status", "user_role",
    ]:
        op.execute(f"DROP TYPE IF EXISTS {enum}")

    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column()")
