"""fixed asset register module.

Revision ID: 0077_fixed_assets
Revises: 0076_org_setup
Create Date: 2026-03-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from financeops.db.append_only import append_only_function_sql, create_trigger_sql, drop_trigger_sql

revision: str = "0077_fixed_assets"
down_revision: str | None = "0076_org_setup"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _tenant_expr() -> str:
    return (
        "COALESCE(NULLIF(current_setting('app.tenant_id', true), ''), "
        "NULLIF(current_setting('app.current_tenant_id', true), ''))::uuid"
    )


def _enable_tenant_rls(table_name: str) -> None:
    op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY {table_name}_tenant_isolation ON {table_name} "
        f"USING (tenant_id = {_tenant_expr()})"
    )


def upgrade() -> None:
    op.create_table(
        "fa_asset_classes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("asset_type", sa.String(length=20), nullable=False),
        sa.Column("default_method", sa.String(length=20), nullable=False),
        sa.Column("default_useful_life_years", sa.Integer(), nullable=True),
        sa.Column("default_residual_pct", sa.Numeric(5, 4), nullable=True),
        sa.Column("it_act_block_number", sa.Integer(), nullable=True),
        sa.Column("it_act_depreciation_rate", sa.Numeric(5, 4), nullable=True),
        sa.Column("coa_asset_account_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("coa_accum_dep_account_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("coa_dep_expense_account_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["iam_tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["entity_id"], ["cp_entities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["coa_asset_account_id"], ["tenant_coa_accounts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["coa_accum_dep_account_id"], ["tenant_coa_accounts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["coa_dep_expense_account_id"], ["tenant_coa_accounts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_fa_asset_classes_tenant_id", "fa_asset_classes", ["tenant_id"], unique=False)
    op.create_index("idx_fa_asset_classes_entity_id", "fa_asset_classes", ["entity_id"], unique=False)
    op.create_index("idx_fa_asset_classes_name", "fa_asset_classes", ["name"], unique=False)

    op.create_table(
        "fa_assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("asset_class_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("asset_code", sa.String(length=100), nullable=False),
        sa.Column("asset_name", sa.String(length=300), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("location", sa.String(length=300), nullable=True),
        sa.Column("serial_number", sa.String(length=200), nullable=True),
        sa.Column("purchase_date", sa.Date(), nullable=False),
        sa.Column("capitalisation_date", sa.Date(), nullable=False),
        sa.Column("original_cost", sa.Numeric(20, 4), nullable=False),
        sa.Column("residual_value", sa.Numeric(20, 4), nullable=False, server_default=sa.text("0")),
        sa.Column("useful_life_years", sa.Numeric(10, 4), nullable=False),
        sa.Column("depreciation_method", sa.String(length=20), nullable=False),
        sa.Column("it_act_block_number", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("disposal_date", sa.Date(), nullable=True),
        sa.Column("disposal_proceeds", sa.Numeric(20, 4), nullable=True),
        sa.Column("gaap_overrides", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["iam_tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["entity_id"], ["cp_entities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["asset_class_id"], ["fa_asset_classes.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "entity_id", "asset_code", name="uq_fa_assets_tenant_entity_code"),
    )
    op.create_index("idx_fa_assets_tenant_id", "fa_assets", ["tenant_id"], unique=False)
    op.create_index("idx_fa_assets_entity_id", "fa_assets", ["entity_id"], unique=False)
    op.create_index("idx_fa_assets_asset_class_id", "fa_assets", ["asset_class_id"], unique=False)
    op.create_index("idx_fa_assets_asset_code", "fa_assets", ["asset_code"], unique=False)
    op.create_index("idx_fa_assets_status", "fa_assets", ["status"], unique=False)

    op.create_table(
        "fa_depreciation_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_date", sa.Date(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("gaap", sa.String(length=20), nullable=False),
        sa.Column("depreciation_method", sa.String(length=20), nullable=False),
        sa.Column("opening_nbv", sa.Numeric(20, 4), nullable=False),
        sa.Column("depreciation_amount", sa.Numeric(20, 4), nullable=False),
        sa.Column("closing_nbv", sa.Numeric(20, 4), nullable=False),
        sa.Column("accumulated_dep", sa.Numeric(20, 4), nullable=False),
        sa.Column("run_reference", sa.String(length=100), nullable=False),
        sa.Column("is_reversal", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["iam_tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["entity_id"], ["cp_entities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["asset_id"], ["fa_assets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_reference", name="uq_fa_depreciation_runs_run_reference"),
    )
    op.create_index("idx_fa_depreciation_runs_tenant_id", "fa_depreciation_runs", ["tenant_id"], unique=False)
    op.create_index("idx_fa_depreciation_runs_entity_id", "fa_depreciation_runs", ["entity_id"], unique=False)
    op.create_index("idx_fa_depreciation_runs_asset_id", "fa_depreciation_runs", ["asset_id"], unique=False)
    op.create_index("idx_fa_depreciation_runs_run_date", "fa_depreciation_runs", ["run_date"], unique=False)

    op.create_table(
        "fa_revaluations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("revaluation_date", sa.Date(), nullable=False),
        sa.Column("pre_revaluation_cost", sa.Numeric(20, 4), nullable=False),
        sa.Column("pre_revaluation_accum_dep", sa.Numeric(20, 4), nullable=False),
        sa.Column("pre_revaluation_nbv", sa.Numeric(20, 4), nullable=False),
        sa.Column("fair_value", sa.Numeric(20, 4), nullable=False),
        sa.Column("revaluation_surplus", sa.Numeric(20, 4), nullable=False),
        sa.Column("method", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["iam_tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["entity_id"], ["cp_entities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["asset_id"], ["fa_assets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_fa_revaluations_tenant_id", "fa_revaluations", ["tenant_id"], unique=False)
    op.create_index("idx_fa_revaluations_entity_id", "fa_revaluations", ["entity_id"], unique=False)
    op.create_index("idx_fa_revaluations_asset_id", "fa_revaluations", ["asset_id"], unique=False)
    op.create_index("idx_fa_revaluations_revaluation_date", "fa_revaluations", ["revaluation_date"], unique=False)

    op.create_table(
        "fa_impairments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("impairment_date", sa.Date(), nullable=False),
        sa.Column("pre_impairment_nbv", sa.Numeric(20, 4), nullable=False),
        sa.Column("recoverable_amount", sa.Numeric(20, 4), nullable=False),
        sa.Column("value_in_use", sa.Numeric(20, 4), nullable=True),
        sa.Column("fvlcts", sa.Numeric(20, 4), nullable=True),
        sa.Column("impairment_loss", sa.Numeric(20, 4), nullable=False),
        sa.Column("discount_rate", sa.Numeric(7, 4), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["iam_tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["entity_id"], ["cp_entities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["asset_id"], ["fa_assets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_fa_impairments_tenant_id", "fa_impairments", ["tenant_id"], unique=False)
    op.create_index("idx_fa_impairments_entity_id", "fa_impairments", ["entity_id"], unique=False)
    op.create_index("idx_fa_impairments_asset_id", "fa_impairments", ["asset_id"], unique=False)
    op.create_index("idx_fa_impairments_impairment_date", "fa_impairments", ["impairment_date"], unique=False)

    _enable_tenant_rls("fa_asset_classes")
    _enable_tenant_rls("fa_assets")
    _enable_tenant_rls("fa_depreciation_runs")
    _enable_tenant_rls("fa_revaluations")
    _enable_tenant_rls("fa_impairments")

    op.execute(sa.text(append_only_function_sql()))
    op.execute(sa.text(create_trigger_sql("fa_depreciation_runs")))
    op.execute(sa.text(create_trigger_sql("fa_revaluations")))
    op.execute(sa.text(create_trigger_sql("fa_impairments")))


def downgrade() -> None:
    op.execute(sa.text(drop_trigger_sql("fa_impairments")))
    op.execute(sa.text(drop_trigger_sql("fa_revaluations")))
    op.execute(sa.text(drop_trigger_sql("fa_depreciation_runs")))

    op.drop_index("idx_fa_impairments_impairment_date", table_name="fa_impairments")
    op.drop_index("idx_fa_impairments_asset_id", table_name="fa_impairments")
    op.drop_index("idx_fa_impairments_entity_id", table_name="fa_impairments")
    op.drop_index("idx_fa_impairments_tenant_id", table_name="fa_impairments")
    op.drop_table("fa_impairments")

    op.drop_index("idx_fa_revaluations_revaluation_date", table_name="fa_revaluations")
    op.drop_index("idx_fa_revaluations_asset_id", table_name="fa_revaluations")
    op.drop_index("idx_fa_revaluations_entity_id", table_name="fa_revaluations")
    op.drop_index("idx_fa_revaluations_tenant_id", table_name="fa_revaluations")
    op.drop_table("fa_revaluations")

    op.drop_index("idx_fa_depreciation_runs_run_date", table_name="fa_depreciation_runs")
    op.drop_index("idx_fa_depreciation_runs_asset_id", table_name="fa_depreciation_runs")
    op.drop_index("idx_fa_depreciation_runs_entity_id", table_name="fa_depreciation_runs")
    op.drop_index("idx_fa_depreciation_runs_tenant_id", table_name="fa_depreciation_runs")
    op.drop_table("fa_depreciation_runs")

    op.drop_index("idx_fa_assets_status", table_name="fa_assets")
    op.drop_index("idx_fa_assets_asset_code", table_name="fa_assets")
    op.drop_index("idx_fa_assets_asset_class_id", table_name="fa_assets")
    op.drop_index("idx_fa_assets_entity_id", table_name="fa_assets")
    op.drop_index("idx_fa_assets_tenant_id", table_name="fa_assets")
    op.drop_table("fa_assets")

    op.drop_index("idx_fa_asset_classes_name", table_name="fa_asset_classes")
    op.drop_index("idx_fa_asset_classes_entity_id", table_name="fa_asset_classes")
    op.drop_index("idx_fa_asset_classes_tenant_id", table_name="fa_asset_classes")
    op.drop_table("fa_asset_classes")
