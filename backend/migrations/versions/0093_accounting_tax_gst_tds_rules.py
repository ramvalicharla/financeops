"""accounting_tax_gst_tds_rules

Revision ID: 0093_acct_tax_gst_tds_rules
Revises: 0091_coa_crosswalk_external_ref
Create Date: 2026-03-28

Creates:
  accounting_gst_rules - mutable GST config
  accounting_tds_rules - mutable TDS config
  accounting_tax_determination_logs - append-only tax determination audit
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

revision: str = "0093_acct_tax_gst_tds_rules"
down_revision: str | None = "0091_coa_crosswalk_external_ref"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "accounting_gst_rules",
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
        sa.Column("account_code", sa.String(length=32), nullable=True),
        sa.Column("gst_type", sa.String(length=8), nullable=False),
        sa.Column("gst_rate", NUMERIC(precision=10, scale=4), nullable=False),
        sa.Column("hsn_sac_code", sa.String(length=8), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
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
        sa.CheckConstraint(
            "gst_type IN ('CGST','SGST','IGST','EXEMPT','NIL')",
            name="ck_accounting_gst_rules_type",
        ),
    )
    op.create_index(
        "ix_accounting_gst_rules_tenant_entity",
        "accounting_gst_rules",
        ["tenant_id", "entity_id"],
    )
    op.create_index(
        "ix_accounting_gst_rules_account_code",
        "accounting_gst_rules",
        ["tenant_id", "account_code"],
    )

    op.create_table(
        "accounting_tds_rules",
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
        sa.Column("vendor_id", UUID(as_uuid=True), nullable=True),
        sa.Column("tds_section", sa.String(length=16), nullable=False),
        sa.Column("section_description", sa.String(length=256), nullable=True),
        sa.Column("tds_rate", NUMERIC(precision=10, scale=4), nullable=False),
        sa.Column("threshold_amount", NUMERIC(precision=20, scale=4), nullable=True),
        sa.Column("surcharge_rate", NUMERIC(precision=10, scale=4), nullable=False, server_default="0"),
        sa.Column("cess_rate", NUMERIC(precision=10, scale=4), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["entity_id"], ["cp_entities.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["vendor_id"], ["accounting_vendors.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["iam_users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_accounting_tds_rules_tenant_entity",
        "accounting_tds_rules",
        ["tenant_id", "entity_id"],
    )
    op.create_index(
        "ix_accounting_tds_rules_vendor",
        "accounting_tds_rules",
        ["tenant_id", "vendor_id"],
    )
    op.create_index(
        "ix_accounting_tds_rules_section",
        "accounting_tds_rules",
        ["tenant_id", "tds_section"],
    )

    op.create_table(
        "accounting_tax_determination_logs",
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
        sa.Column("jv_id", UUID(as_uuid=True), nullable=False),
        sa.Column("jv_version", sa.Integer(), nullable=False),
        sa.Column("tax_type", sa.String(length=16), nullable=False),
        sa.Column("gst_sub_type", sa.String(length=8), nullable=True),
        sa.Column("tds_section", sa.String(length=16), nullable=True),
        sa.Column("supplier_state_code", sa.String(length=2), nullable=True),
        sa.Column("buyer_state_code", sa.String(length=2), nullable=True),
        sa.Column("base_amount", NUMERIC(precision=20, scale=4), nullable=False),
        sa.Column("tax_amount", NUMERIC(precision=20, scale=4), nullable=False),
        sa.Column("cgst_amount", NUMERIC(precision=20, scale=4), nullable=True),
        sa.Column("sgst_amount", NUMERIC(precision=20, scale=4), nullable=True),
        sa.Column("igst_amount", NUMERIC(precision=20, scale=4), nullable=True),
        sa.Column("tds_amount", NUMERIC(precision=20, scale=4), nullable=True),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("outcome_reason", sa.Text(), nullable=True),
        sa.Column("gst_rule_id", UUID(as_uuid=True), nullable=True),
        sa.Column("tds_rule_id", UUID(as_uuid=True), nullable=True),
        sa.Column(
            "determined_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["jv_id"], ["accounting_jv_aggregates.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["gst_rule_id"], ["accounting_gst_rules.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tds_rule_id"], ["accounting_tds_rules.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "tax_type IN ('GST','TDS','NONE','MANUAL_REQUIRED')",
            name="ck_accounting_tax_determination_logs_type",
        ),
        sa.CheckConstraint(
            "outcome IN ('SUCCESS','MANUAL_FLAG','SKIPPED','ERROR')",
            name="ck_accounting_tax_determination_logs_outcome",
        ),
    )
    op.create_index(
        "ix_tax_determination_logs_jv_id",
        "accounting_tax_determination_logs",
        ["jv_id"],
    )
    op.create_index(
        "ix_tax_determination_logs_tenant_id",
        "accounting_tax_determination_logs",
        ["tenant_id"],
    )
    op.create_index(
        "ix_tax_determination_logs_outcome",
        "accounting_tax_determination_logs",
        ["tenant_id", "outcome"],
    )

    op.execute("ALTER TABLE accounting_gst_rules ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE accounting_gst_rules FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON accounting_gst_rules "
        "USING (tenant_id = COALESCE(current_setting('app.tenant_id', true), "
        "current_setting('app.current_tenant_id', true))::uuid)"
    )

    op.execute("ALTER TABLE accounting_tds_rules ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE accounting_tds_rules FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON accounting_tds_rules "
        "USING (tenant_id = COALESCE(current_setting('app.tenant_id', true), "
        "current_setting('app.current_tenant_id', true))::uuid)"
    )

    op.execute("ALTER TABLE accounting_tax_determination_logs ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE accounting_tax_determination_logs FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON accounting_tax_determination_logs "
        "USING (tenant_id = COALESCE(current_setting('app.tenant_id', true), "
        "current_setting('app.current_tenant_id', true))::uuid)"
    )

    op.execute(append_only_function_sql())
    op.execute(drop_trigger_sql("accounting_tax_determination_logs"))
    op.execute(create_trigger_sql("accounting_tax_determination_logs"))


def downgrade() -> None:
    op.execute(drop_trigger_sql("accounting_tax_determination_logs"))
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON accounting_tax_determination_logs")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON accounting_tds_rules")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON accounting_gst_rules")

    op.drop_index(
        "ix_tax_determination_logs_outcome",
        table_name="accounting_tax_determination_logs",
    )
    op.drop_index(
        "ix_tax_determination_logs_tenant_id",
        table_name="accounting_tax_determination_logs",
    )
    op.drop_index(
        "ix_tax_determination_logs_jv_id",
        table_name="accounting_tax_determination_logs",
    )
    op.drop_table("accounting_tax_determination_logs")

    op.drop_index("ix_accounting_tds_rules_section", table_name="accounting_tds_rules")
    op.drop_index("ix_accounting_tds_rules_vendor", table_name="accounting_tds_rules")
    op.drop_index("ix_accounting_tds_rules_tenant_entity", table_name="accounting_tds_rules")
    op.drop_table("accounting_tds_rules")

    op.drop_index("ix_accounting_gst_rules_account_code", table_name="accounting_gst_rules")
    op.drop_index("ix_accounting_gst_rules_tenant_entity", table_name="accounting_gst_rules")
    op.drop_table("accounting_gst_rules")
