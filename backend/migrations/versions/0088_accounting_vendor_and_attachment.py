"""accounting_vendor_and_attachment_metadata

Revision ID: 0088_acct_vendor_attach
Revises: 0087_accounting_approval_and_sla
Create Date: 2026-03-28

Creates:
  accounting_vendors - mutable vendor master
  accounting_attachments - append-only attachment metadata
  erp_attachment_links - append-only ERP transport linkage
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import NUMERIC, UUID

from financeops.db.append_only import (
    append_only_function_sql,
    create_trigger_sql,
    drop_trigger_sql,
)

revision: str = "0088_acct_vendor_attach"
down_revision: str | None = "0087_accounting_approval_and_sla"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "accounting_vendors",
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
        sa.Column("entity_id", UUID(as_uuid=True), nullable=False),
        sa.Column("vendor_name", sa.String(length=256), nullable=False),
        sa.Column("vendor_code", sa.String(length=64), nullable=True),
        sa.Column("gstin", sa.String(length=15), nullable=True),
        sa.Column("pan", sa.String(length=10), nullable=True),
        sa.Column("tan", sa.String(length=10), nullable=True),
        sa.Column("tds_section", sa.String(length=16), nullable=True),
        sa.Column("tds_rate", NUMERIC(precision=10, scale=4), nullable=True),
        sa.Column("tds_threshold", NUMERIC(precision=20, scale=4), nullable=True),
        sa.Column("email", sa.String(length=256), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("state_code", sa.String(length=2), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("erp_vendor_id", sa.String(length=128), nullable=True),
        sa.Column("erp_connector_type", sa.String(length=32), nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["entity_id"], ["cp_entities.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["iam_users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("ix_accounting_vendors_tenant_id", "accounting_vendors", ["tenant_id"])
    op.create_index("ix_accounting_vendors_entity_id", "accounting_vendors", ["entity_id"])
    op.create_index("ix_accounting_vendors_gstin", "accounting_vendors", ["tenant_id", "gstin"])
    op.create_index("ix_accounting_vendors_pan", "accounting_vendors", ["tenant_id", "pan"])
    op.create_index(
        "ix_accounting_vendors_vendor_code",
        "accounting_vendors",
        ["tenant_id", "vendor_code"],
        unique=True,
        postgresql_where=sa.text("vendor_code IS NOT NULL"),
    )

    op.create_table(
        "accounting_attachments",
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
        sa.Column("jv_id", UUID(as_uuid=True), nullable=True),
        sa.Column("vendor_id", UUID(as_uuid=True), nullable=True),
        sa.Column("r2_key", sa.String(length=512), nullable=False),
        sa.Column("r2_bucket", sa.String(length=128), nullable=True),
        sa.Column("filename", sa.String(length=256), nullable=False),
        sa.Column("mime_type", sa.String(length=128), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256_hash", sa.String(length=64), nullable=False),
        sa.Column("document_type", sa.String(length=32), nullable=True),
        sa.Column("worm_locked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("worm_locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scan_status", sa.String(length=16), nullable=True),
        sa.Column("scan_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("uploaded_by", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["jv_id"], ["accounting_jv_aggregates.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["vendor_id"], ["accounting_vendors.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["uploaded_by"], ["iam_users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("ix_accounting_attachments_tenant_id", "accounting_attachments", ["tenant_id"])
    op.create_index("ix_accounting_attachments_jv_id", "accounting_attachments", ["jv_id"])
    op.create_index("ix_accounting_attachments_sha256", "accounting_attachments", ["tenant_id", "sha256_hash"])
    op.create_index("ix_accounting_attachments_vendor_id", "accounting_attachments", ["vendor_id"])

    op.create_table(
        "erp_attachment_links",
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
        sa.Column("attachment_id", UUID(as_uuid=True), nullable=False),
        sa.Column("connector_type", sa.String(length=32), nullable=False),
        sa.Column("erp_document_id", sa.String(length=256), nullable=True),
        sa.Column("erp_journal_id", sa.String(length=256), nullable=True),
        sa.Column("push_status", sa.String(length=16), nullable=False, server_default="PENDING"),
        sa.Column("push_error", sa.Text(), nullable=True),
        sa.Column("pushed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["attachment_id"], ["accounting_attachments.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("ix_erp_attachment_links_attachment_id", "erp_attachment_links", ["attachment_id"])
    op.create_index("ix_erp_attachment_links_tenant_id", "erp_attachment_links", ["tenant_id"])

    op.execute("ALTER TABLE accounting_vendors ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE accounting_vendors FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON accounting_vendors "
        "USING (tenant_id = COALESCE(current_setting('app.tenant_id', true), "
        "current_setting('app.current_tenant_id', true))::uuid)"
    )

    op.execute("ALTER TABLE accounting_attachments ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE accounting_attachments FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON accounting_attachments "
        "USING (tenant_id = COALESCE(current_setting('app.tenant_id', true), "
        "current_setting('app.current_tenant_id', true))::uuid)"
    )

    op.execute("ALTER TABLE erp_attachment_links ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE erp_attachment_links FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON erp_attachment_links "
        "USING (tenant_id = COALESCE(current_setting('app.tenant_id', true), "
        "current_setting('app.current_tenant_id', true))::uuid)"
    )

    op.execute(append_only_function_sql())
    op.execute(drop_trigger_sql("accounting_attachments"))
    op.execute(create_trigger_sql("accounting_attachments"))
    op.execute(drop_trigger_sql("erp_attachment_links"))
    op.execute(create_trigger_sql("erp_attachment_links"))


def downgrade() -> None:
    op.execute(drop_trigger_sql("erp_attachment_links"))
    op.execute(drop_trigger_sql("accounting_attachments"))

    op.execute("DROP POLICY IF EXISTS tenant_isolation ON erp_attachment_links")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON accounting_attachments")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON accounting_vendors")

    op.drop_index("ix_erp_attachment_links_tenant_id", table_name="erp_attachment_links")
    op.drop_index("ix_erp_attachment_links_attachment_id", table_name="erp_attachment_links")
    op.drop_table("erp_attachment_links")

    op.drop_index("ix_accounting_attachments_vendor_id", table_name="accounting_attachments")
    op.drop_index("ix_accounting_attachments_sha256", table_name="accounting_attachments")
    op.drop_index("ix_accounting_attachments_jv_id", table_name="accounting_attachments")
    op.drop_index("ix_accounting_attachments_tenant_id", table_name="accounting_attachments")
    op.drop_table("accounting_attachments")

    op.drop_index("ix_accounting_vendors_vendor_code", table_name="accounting_vendors")
    op.drop_index("ix_accounting_vendors_pan", table_name="accounting_vendors")
    op.drop_index("ix_accounting_vendors_gstin", table_name="accounting_vendors")
    op.drop_index("ix_accounting_vendors_entity_id", table_name="accounting_vendors")
    op.drop_index("ix_accounting_vendors_tenant_id", table_name="accounting_vendors")
    op.drop_table("accounting_vendors")
