"""inbound_email_vendor_portal_intake

Revision ID: 0098_inbound_email_vendor_portal
Revises: 0097_erp_webhook_event_ingest
Create Date: 2026-03-29

Creates:
  accounting_inbound_email_messages
  vendor_portal_submissions
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0098_inbound_email_vendor_portal"
down_revision: str | None = "0097_erp_webhook_event_ingest"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _enable_rls(table_name: str) -> None:
    op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation ON {table_name} "
        "USING (tenant_id = COALESCE(current_setting('app.tenant_id', true), "
        "current_setting('app.current_tenant_id', true))::uuid)"
    )


def upgrade() -> None:
    op.create_table(
        "accounting_inbound_email_messages",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("entity_id", UUID(as_uuid=True), nullable=True),
        sa.Column("message_id", sa.String(length=512), nullable=False),
        sa.Column("sender_email", sa.String(length=256), nullable=False),
        sa.Column("sender_name", sa.String(length=256), nullable=True),
        sa.Column("subject", sa.Text(), nullable=True),
        sa.Column("sender_whitelisted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("processing_status", sa.String(length=32), nullable=False, server_default="PENDING"),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processing_error", sa.Text(), nullable=True),
        sa.Column("attachment_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("auto_reply_sent", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("raw_metadata", JSONB, nullable=True),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["entity_id"], ["cp_entities.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "message_id", name="uq_inbound_email_message_id"),
        sa.CheckConstraint(
            "processing_status IN ('PENDING','PROCESSING','PROCESSED','REJECTED','FAILED')",
            name="ck_accounting_inbound_email_messages_processing_status",
        ),
    )
    op.create_index(
        "ix_inbound_email_tenant_id",
        "accounting_inbound_email_messages",
        ["tenant_id"],
    )
    op.create_index(
        "ix_inbound_email_sender",
        "accounting_inbound_email_messages",
        ["tenant_id", "sender_email"],
    )
    op.create_index(
        "ix_inbound_email_status",
        "accounting_inbound_email_messages",
        ["tenant_id", "processing_status"],
    )
    op.create_index(
        "ix_inbound_email_entity_id",
        "accounting_inbound_email_messages",
        ["entity_id"],
    )

    op.create_table(
        "vendor_portal_submissions",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("entity_id", UUID(as_uuid=True), nullable=True),
        sa.Column("vendor_id", UUID(as_uuid=True), nullable=True),
        sa.Column("reference_id", sa.String(length=64), nullable=False),
        sa.Column("submitter_email", sa.String(length=256), nullable=False),
        sa.Column("submitter_name", sa.String(length=256), nullable=True),
        sa.Column("vendor_email_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("r2_key", sa.String(length=512), nullable=True),
        sa.Column("filename", sa.String(length=256), nullable=True),
        sa.Column("mime_type", sa.String(length=128), nullable=True),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("sha256_hash", sa.String(length=64), nullable=True),
        sa.Column("scan_status", sa.String(length=16), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="RECEIVED"),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("jv_id", UUID(as_uuid=True), nullable=True),
        sa.Column(
            "submitted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["entity_id"], ["cp_entities.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["vendor_id"], ["accounting_vendors.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["jv_id"], ["accounting_jv_aggregates.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("reference_id", name="uq_vendor_portal_submissions_reference_id"),
        sa.CheckConstraint(
            "status IN ('RECEIVED','UNDER_REVIEW','ACCEPTED','REJECTED')",
            name="ck_vendor_portal_submissions_status",
        ),
    )
    op.create_index(
        "ix_vendor_portal_submissions_tenant_id",
        "vendor_portal_submissions",
        ["tenant_id"],
    )
    op.create_index(
        "ix_vendor_portal_submissions_vendor_id",
        "vendor_portal_submissions",
        ["vendor_id"],
    )
    op.create_index(
        "ix_vendor_portal_submissions_reference_id",
        "vendor_portal_submissions",
        ["reference_id"],
        unique=True,
    )
    op.create_index(
        "ix_vendor_portal_submissions_status",
        "vendor_portal_submissions",
        ["tenant_id", "status"],
    )
    op.create_index(
        "ix_vendor_portal_submissions_submitter_email",
        "vendor_portal_submissions",
        ["tenant_id", "submitter_email"],
    )

    for table_name in (
        "accounting_inbound_email_messages",
        "vendor_portal_submissions",
    ):
        _enable_rls(table_name)


def downgrade() -> None:
    for table_name in (
        "vendor_portal_submissions",
        "accounting_inbound_email_messages",
    ):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table_name}")

    op.drop_index(
        "ix_vendor_portal_submissions_submitter_email",
        table_name="vendor_portal_submissions",
    )
    op.drop_index(
        "ix_vendor_portal_submissions_status",
        table_name="vendor_portal_submissions",
    )
    op.drop_index(
        "ix_vendor_portal_submissions_reference_id",
        table_name="vendor_portal_submissions",
    )
    op.drop_index(
        "ix_vendor_portal_submissions_vendor_id",
        table_name="vendor_portal_submissions",
    )
    op.drop_index(
        "ix_vendor_portal_submissions_tenant_id",
        table_name="vendor_portal_submissions",
    )
    op.drop_table("vendor_portal_submissions")

    op.drop_index(
        "ix_inbound_email_entity_id",
        table_name="accounting_inbound_email_messages",
    )
    op.drop_index(
        "ix_inbound_email_status",
        table_name="accounting_inbound_email_messages",
    )
    op.drop_index(
        "ix_inbound_email_sender",
        table_name="accounting_inbound_email_messages",
    )
    op.drop_index(
        "ix_inbound_email_tenant_id",
        table_name="accounting_inbound_email_messages",
    )
    op.drop_table("accounting_inbound_email_messages")
