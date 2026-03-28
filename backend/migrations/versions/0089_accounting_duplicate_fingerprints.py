"""accounting_duplicate_fingerprints

Revision ID: 0089_acct_duplicate_fprints
Revises: 0088_acct_vendor_attach
Create Date: 2026-03-28

Creates accounting_duplicate_fingerprints as append-only duplicate flags.
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

revision: str = "0089_acct_duplicate_fprints"
down_revision: str | None = "0088_acct_vendor_attach"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "accounting_duplicate_fingerprints",
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
        sa.Column("jv_id", UUID(as_uuid=True), nullable=True),
        sa.Column("detection_layer", sa.Integer(), nullable=False),
        sa.Column("file_hash", sa.String(length=64), nullable=True),
        sa.Column("invoice_number", sa.String(length=128), nullable=True),
        sa.Column("vendor_gstin", sa.String(length=15), nullable=True),
        sa.Column("layer2_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("vendor_id", UUID(as_uuid=True), nullable=True),
        sa.Column("amount_bucket", NUMERIC(precision=20, scale=4), nullable=True),
        sa.Column("date_bucket", sa.Date(), nullable=True),
        sa.Column("layer3_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("conflict_attachment_id", UUID(as_uuid=True), nullable=True),
        sa.Column("conflict_jv_id", UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(length=16), nullable=False, server_default="FLAGGED"),
        sa.Column("action_reason", sa.Text(), nullable=True),
        sa.Column("action_by", UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["attachment_id"], ["accounting_attachments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["jv_id"], ["accounting_jv_aggregates.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["conflict_attachment_id"], ["accounting_attachments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["conflict_jv_id"], ["accounting_jv_aggregates.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["action_by"], ["iam_users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("detection_layer IN (1,2,3)", name="ck_duplicate_detection_layer"),
        sa.CheckConstraint(
            "action IN ('FLAGGED','SKIPPED','OVERRIDDEN','RELATED')",
            name="ck_duplicate_action",
        ),
    )

    op.create_index(
        "ix_duplicate_fingerprints_tenant_id",
        "accounting_duplicate_fingerprints",
        ["tenant_id"],
    )
    op.create_index(
        "ix_duplicate_fingerprints_attachment_id",
        "accounting_duplicate_fingerprints",
        ["attachment_id"],
    )
    op.create_index(
        "ix_duplicate_fingerprints_file_hash",
        "accounting_duplicate_fingerprints",
        ["tenant_id", "file_hash"],
    )
    op.create_index(
        "ix_duplicate_fingerprints_layer2",
        "accounting_duplicate_fingerprints",
        ["tenant_id", "layer2_fingerprint"],
    )
    op.create_index(
        "ix_duplicate_fingerprints_layer3",
        "accounting_duplicate_fingerprints",
        ["tenant_id", "layer3_fingerprint"],
    )
    op.create_index(
        "ix_duplicate_fingerprints_action",
        "accounting_duplicate_fingerprints",
        ["tenant_id", "action"],
    )

    op.execute("ALTER TABLE accounting_duplicate_fingerprints ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE accounting_duplicate_fingerprints FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON accounting_duplicate_fingerprints "
        "USING (tenant_id = COALESCE(current_setting('app.tenant_id', true), "
        "current_setting('app.current_tenant_id', true))::uuid)"
    )

    op.execute(append_only_function_sql())
    op.execute(drop_trigger_sql("accounting_duplicate_fingerprints"))
    op.execute(create_trigger_sql("accounting_duplicate_fingerprints"))


def downgrade() -> None:
    op.execute(drop_trigger_sql("accounting_duplicate_fingerprints"))
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON accounting_duplicate_fingerprints")

    op.drop_index(
        "ix_duplicate_fingerprints_action",
        table_name="accounting_duplicate_fingerprints",
    )
    op.drop_index(
        "ix_duplicate_fingerprints_layer3",
        table_name="accounting_duplicate_fingerprints",
    )
    op.drop_index(
        "ix_duplicate_fingerprints_layer2",
        table_name="accounting_duplicate_fingerprints",
    )
    op.drop_index(
        "ix_duplicate_fingerprints_file_hash",
        table_name="accounting_duplicate_fingerprints",
    )
    op.drop_index(
        "ix_duplicate_fingerprints_attachment_id",
        table_name="accounting_duplicate_fingerprints",
    )
    op.drop_index(
        "ix_duplicate_fingerprints_tenant_id",
        table_name="accounting_duplicate_fingerprints",
    )
    op.drop_table("accounting_duplicate_fingerprints")
