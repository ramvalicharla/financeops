"""Phase 1D.5 Fixed Assets Core

Revision ID: 0010_phase1d5_fixed_assets_core
Revises: 0009_phase1d4_prepaid_core
Create Date: 2026-03-07 00:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from financeops.db.append_only import append_only_function_sql, create_trigger_sql, drop_trigger_sql

revision: str = "0010_phase1d5_fixed_assets_core"
down_revision: str | None = "0009_phase1d4_prepaid_core"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "far_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_signature", sa.String(length=64), nullable=False),
        sa.Column("initiated_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("configuration_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("workflow_id", sa.String(length=128), nullable=False),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "request_signature", name="uq_far_runs_tenant_signature"),
    )
    op.create_index("idx_far_runs_tenant_created", "far_runs", ["tenant_id", "created_at"])

    op.create_table(
        "far_run_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_seq", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["far_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "event_seq", name="uq_far_run_events_seq"),
        sa.UniqueConstraint("run_id", "event_type", "idempotency_key", name="uq_far_run_events_idempotent"),
    )
    op.create_index("idx_far_run_events_tenant_run", "far_run_events", ["tenant_id", "run_id", "event_seq"])

    op.create_table(
        "assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("asset_code", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("entity_id", sa.String(length=128), nullable=False),
        sa.Column("asset_class", sa.String(length=64), nullable=False),
        sa.Column("asset_currency", sa.String(length=3), nullable=False),
        sa.Column("reporting_currency", sa.String(length=3), nullable=False),
        sa.Column("capitalization_date", sa.Date(), nullable=False),
        sa.Column("in_service_date", sa.Date(), nullable=False),
        sa.Column("capitalized_amount_asset_currency", sa.Numeric(20, 6), nullable=False),
        sa.Column("depreciation_method", sa.String(length=32), nullable=False),
        sa.Column("useful_life_months", sa.Integer(), nullable=True),
        sa.Column("reducing_balance_rate_annual", sa.Numeric(20, 6), nullable=True),
        sa.Column("residual_value_reporting_currency", sa.Numeric(20, 6), nullable=False),
        sa.Column("rate_mode", sa.String(length=32), nullable=False),
        sa.Column("source_acquisition_reference", sa.String(length=255), nullable=False),
        sa.Column("parent_reference_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_reference_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.Column("supersedes_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["supersedes_id"], ["assets.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "(depreciation_method != 'straight_line') OR "
            "(useful_life_months IS NOT NULL AND reducing_balance_rate_annual IS NULL)",
            name="ck_assets_straight_line_params",
        ),
        sa.CheckConstraint(
            "(depreciation_method != 'reducing_balance') OR "
            "(reducing_balance_rate_annual IS NOT NULL)",
            name="ck_assets_reducing_balance_params",
        ),
        sa.CheckConstraint(
            "(depreciation_method != 'non_depreciable') OR "
            "(useful_life_months IS NULL AND reducing_balance_rate_annual IS NULL)",
            name="ck_assets_non_depreciable_params",
        ),
    )
    op.create_index("idx_assets_tenant_code", "assets", ["tenant_id", "asset_code", "created_at"])
    op.create_index("idx_assets_tenant_source", "assets", ["tenant_id", "source_acquisition_reference"])

    op.create_table(
        "asset_depreciation_schedule",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("period_seq", sa.Integer(), nullable=False),
        sa.Column("depreciation_date", sa.Date(), nullable=False),
        sa.Column("depreciation_period_year", sa.Integer(), nullable=False),
        sa.Column("depreciation_period_month", sa.Integer(), nullable=False),
        sa.Column("schedule_version_token", sa.String(length=64), nullable=False),
        sa.Column("opening_carrying_amount_reporting_currency", sa.Numeric(20, 6), nullable=False),
        sa.Column("depreciation_amount_reporting_currency", sa.Numeric(20, 6), nullable=False),
        sa.Column("cumulative_depreciation_reporting_currency", sa.Numeric(20, 6), nullable=False),
        sa.Column("closing_carrying_amount_reporting_currency", sa.Numeric(20, 6), nullable=False),
        sa.Column("fx_rate_used", sa.Numeric(20, 6), nullable=False),
        sa.Column("fx_rate_date", sa.Date(), nullable=False),
        sa.Column("fx_rate_source", sa.String(length=64), nullable=False),
        sa.Column("schedule_status", sa.String(length=32), nullable=False),
        sa.Column("source_acquisition_reference", sa.String(length=255), nullable=False),
        sa.Column("parent_reference_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_reference_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["far_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id",
            "asset_id",
            "depreciation_date",
            "schedule_version_token",
            name="uq_asset_schedule_date_version",
        ),
        sa.UniqueConstraint(
            "run_id",
            "asset_id",
            "period_seq",
            "schedule_version_token",
            name="uq_asset_schedule_period_version",
        ),
    )
    op.create_index(
        "idx_asset_schedule_tenant_run",
        "asset_depreciation_schedule",
        ["tenant_id", "run_id", "depreciation_date"],
    )
    op.create_index(
        "idx_asset_schedule_tenant_asset",
        "asset_depreciation_schedule",
        ["tenant_id", "asset_id"],
    )

    op.create_table(
        "asset_impairments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("impairment_date", sa.Date(), nullable=False),
        sa.Column("impairment_amount_reporting_currency", sa.Numeric(20, 6), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("prior_schedule_version_token", sa.String(length=64), nullable=False),
        sa.Column("new_schedule_version_token", sa.String(length=64), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("fx_rate_used", sa.Numeric(20, 6), nullable=False),
        sa.Column("fx_rate_date", sa.Date(), nullable=False),
        sa.Column("fx_rate_source", sa.String(length=64), nullable=False),
        sa.Column("source_acquisition_reference", sa.String(length=255), nullable=False),
        sa.Column("parent_reference_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_reference_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.Column("supersedes_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["far_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["supersedes_id"], ["asset_impairments.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id",
            "asset_id",
            "impairment_date",
            "idempotency_key",
            name="uq_asset_impairments_idempotent",
        ),
    )
    op.create_index(
        "idx_asset_impairments_tenant_run",
        "asset_impairments",
        ["tenant_id", "run_id", "impairment_date"],
    )
    op.create_index(
        "idx_asset_impairments_tenant_asset",
        "asset_impairments",
        ["tenant_id", "asset_id"],
    )

    op.create_table(
        "asset_disposals",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("disposal_date", sa.Date(), nullable=False),
        sa.Column("proceeds_reporting_currency", sa.Numeric(20, 6), nullable=False),
        sa.Column("disposal_cost_reporting_currency", sa.Numeric(20, 6), nullable=False),
        sa.Column("carrying_amount_reporting_currency", sa.Numeric(20, 6), nullable=False),
        sa.Column("gain_loss_reporting_currency", sa.Numeric(20, 6), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("prior_schedule_version_token", sa.String(length=64), nullable=False),
        sa.Column("new_schedule_version_token", sa.String(length=64), nullable=False),
        sa.Column("fx_rate_used", sa.Numeric(20, 6), nullable=False),
        sa.Column("fx_rate_date", sa.Date(), nullable=False),
        sa.Column("fx_rate_source", sa.String(length=64), nullable=False),
        sa.Column("source_acquisition_reference", sa.String(length=255), nullable=False),
        sa.Column("parent_reference_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_reference_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.Column("supersedes_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["far_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["supersedes_id"], ["asset_disposals.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id",
            "asset_id",
            "disposal_date",
            "idempotency_key",
            name="uq_asset_disposals_idempotent",
        ),
    )
    op.create_index(
        "idx_asset_disposals_tenant_run",
        "asset_disposals",
        ["tenant_id", "run_id", "disposal_date"],
    )
    op.create_index(
        "idx_asset_disposals_tenant_asset",
        "asset_disposals",
        ["tenant_id", "asset_id"],
    )

    op.create_table(
        "asset_journal_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("depreciation_schedule_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("impairment_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("disposal_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("journal_reference", sa.String(length=128), nullable=False),
        sa.Column("line_seq", sa.Integer(), nullable=False),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("debit_account", sa.String(length=64), nullable=False),
        sa.Column("credit_account", sa.String(length=64), nullable=False),
        sa.Column("amount_reporting_currency", sa.Numeric(20, 6), nullable=False),
        sa.Column("source_acquisition_reference", sa.String(length=255), nullable=False),
        sa.Column("parent_reference_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_reference_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["far_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["depreciation_schedule_id"], ["asset_depreciation_schedule.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["impairment_id"], ["asset_impairments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["disposal_id"], ["asset_disposals.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "journal_reference", "line_seq", name="uq_asset_journal_run_ref_line"),
        sa.CheckConstraint(
            "(CASE WHEN depreciation_schedule_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN impairment_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN disposal_id IS NOT NULL THEN 1 ELSE 0 END) = 1",
            name="ck_asset_journal_exactly_one_source",
        ),
    )
    op.create_index(
        "idx_asset_journal_tenant_run",
        "asset_journal_entries",
        ["tenant_id", "run_id", "entry_date"],
    )
    op.create_index(
        "idx_asset_journal_tenant_asset",
        "asset_journal_entries",
        ["tenant_id", "asset_id"],
    )

    far_tables = [
        "far_runs",
        "far_run_events",
        "assets",
        "asset_depreciation_schedule",
        "asset_impairments",
        "asset_disposals",
        "asset_journal_entries",
    ]

    for table_name in far_tables:
        op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY {table_name}_tenant_isolation
              ON {table_name}
              USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
            """
        )

    op.execute(append_only_function_sql())
    for table_name in far_tables:
        op.execute(drop_trigger_sql(table_name))
        op.execute(create_trigger_sql(table_name))


def downgrade() -> None:
    far_tables = [
        "asset_journal_entries",
        "asset_disposals",
        "asset_impairments",
        "asset_depreciation_schedule",
        "assets",
        "far_run_events",
        "far_runs",
    ]

    for table_name in far_tables:
        op.execute(drop_trigger_sql(table_name))
        op.drop_table(table_name)
