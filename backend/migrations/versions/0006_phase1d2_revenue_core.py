"""Phase 1D.2 Revenue Recognition Core

Revision ID: 0006_phase1d2_revenue_core
Revises: 0005_phase1c_consol
Create Date: 2026-03-07 00:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from financeops.db.append_only import append_only_function_sql, create_trigger_sql, drop_trigger_sql

revision: str = "0006_phase1d2_revenue_core"
down_revision: str | None = "0005_phase1c_consol"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "revenue_runs",
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
        sa.UniqueConstraint("tenant_id", "request_signature", name="uq_revenue_runs_tenant_signature"),
    )
    op.create_index("idx_revenue_runs_tenant_created", "revenue_runs", ["tenant_id", "created_at"])

    op.create_table(
        "revenue_run_events",
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
        sa.ForeignKeyConstraint(["run_id"], ["revenue_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "event_seq", name="uq_revenue_run_events_seq"),
        sa.UniqueConstraint(
            "run_id",
            "event_type",
            "idempotency_key",
            name="uq_revenue_run_events_idempotent",
        ),
    )
    op.create_index(
        "idx_revenue_run_events_tenant_run",
        "revenue_run_events",
        ["tenant_id", "run_id", "event_seq"],
    )

    op.create_table(
        "revenue_contracts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("contract_number", sa.String(length=128), nullable=False),
        sa.Column("customer_id", sa.String(length=128), nullable=False),
        sa.Column("contract_currency", sa.String(length=3), nullable=False),
        sa.Column("contract_start_date", sa.Date(), nullable=False),
        sa.Column("contract_end_date", sa.Date(), nullable=False),
        sa.Column("total_contract_value", sa.Numeric(20, 6), nullable=False),
        sa.Column("source_contract_reference", sa.String(length=255), nullable=False),
        sa.Column("policy_code", sa.String(length=64), nullable=False),
        sa.Column("policy_version", sa.String(length=64), nullable=False),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.Column("supersedes_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["supersedes_id"], ["revenue_contracts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_revenue_contracts_tenant_number",
        "revenue_contracts",
        ["tenant_id", "contract_number", "created_at"],
    )
    op.create_index(
        "idx_revenue_contracts_tenant_source",
        "revenue_contracts",
        ["tenant_id", "source_contract_reference"],
    )

    op.create_table(
        "revenue_performance_obligations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("contract_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("obligation_code", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("standalone_selling_price", sa.Numeric(20, 6), nullable=False),
        sa.Column("allocation_basis", sa.String(length=64), nullable=False),
        sa.Column("recognition_method", sa.String(length=64), nullable=False),
        sa.Column("source_contract_reference", sa.String(length=255), nullable=False),
        sa.Column("parent_reference_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_reference_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.Column("supersedes_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["contract_id"], ["revenue_contracts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["supersedes_id"], ["revenue_performance_obligations.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_revenue_obligations_contract",
        "revenue_performance_obligations",
        ["tenant_id", "contract_id"],
    )
    op.create_index(
        "idx_revenue_obligations_method",
        "revenue_performance_obligations",
        ["tenant_id", "recognition_method"],
    )

    op.create_table(
        "revenue_contract_line_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("contract_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("obligation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("line_code", sa.String(length=128), nullable=False),
        sa.Column("line_amount", sa.Numeric(20, 6), nullable=False),
        sa.Column("line_currency", sa.String(length=3), nullable=False),
        sa.Column("milestone_reference", sa.String(length=255), nullable=True),
        sa.Column("usage_reference", sa.String(length=255), nullable=True),
        sa.Column("source_contract_reference", sa.String(length=255), nullable=False),
        sa.Column("parent_reference_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_reference_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.Column("supersedes_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["contract_id"], ["revenue_contracts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["obligation_id"], ["revenue_performance_obligations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["supersedes_id"], ["revenue_contract_line_items.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_revenue_line_items_contract",
        "revenue_contract_line_items",
        ["tenant_id", "contract_id"],
    )
    op.create_index(
        "idx_revenue_line_items_obligation",
        "revenue_contract_line_items",
        ["tenant_id", "obligation_id"],
    )

    op.create_table(
        "revenue_schedules",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("contract_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("obligation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("contract_line_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recognition_date", sa.Date(), nullable=False),
        sa.Column("recognition_period_year", sa.Integer(), nullable=False),
        sa.Column("recognition_period_month", sa.Integer(), nullable=False),
        sa.Column("recognition_method", sa.String(length=64), nullable=False),
        sa.Column("base_amount_contract_currency", sa.Numeric(20, 6), nullable=False),
        sa.Column("fx_rate_used", sa.Numeric(20, 6), nullable=False),
        sa.Column("recognized_amount_reporting_currency", sa.Numeric(20, 6), nullable=False),
        sa.Column("cumulative_recognized_reporting_currency", sa.Numeric(20, 6), nullable=False),
        sa.Column("schedule_status", sa.String(length=32), nullable=False),
        sa.Column("source_contract_reference", sa.String(length=255), nullable=False),
        sa.Column("parent_reference_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_reference_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["revenue_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["contract_id"], ["revenue_contracts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["obligation_id"], ["revenue_performance_obligations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["contract_line_item_id"], ["revenue_contract_line_items.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id",
            "contract_line_item_id",
            "recognition_date",
            name="uq_revenue_schedules_natural",
        ),
    )
    op.create_index(
        "idx_revenue_schedules_run",
        "revenue_schedules",
        ["tenant_id", "run_id", "recognition_date"],
    )
    op.create_index(
        "idx_revenue_schedules_contract",
        "revenue_schedules",
        ["tenant_id", "contract_id"],
    )

    op.create_table(
        "revenue_journal_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("contract_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("obligation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("schedule_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("journal_reference", sa.String(length=128), nullable=False),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("debit_account", sa.String(length=64), nullable=False),
        sa.Column("credit_account", sa.String(length=64), nullable=False),
        sa.Column("amount_reporting_currency", sa.Numeric(20, 6), nullable=False),
        sa.Column("source_contract_reference", sa.String(length=255), nullable=False),
        sa.Column("parent_reference_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_reference_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["revenue_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["contract_id"], ["revenue_contracts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["obligation_id"], ["revenue_performance_obligations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["schedule_id"], ["revenue_schedules.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_revenue_journal_run",
        "revenue_journal_entries",
        ["tenant_id", "run_id", "entry_date"],
    )
    op.create_index(
        "idx_revenue_journal_contract",
        "revenue_journal_entries",
        ["tenant_id", "contract_id"],
    )

    op.create_table(
        "revenue_adjustments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("contract_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("adjustment_type", sa.String(length=64), nullable=False),
        sa.Column("adjustment_reason", sa.Text(), nullable=False),
        sa.Column("prior_schedule_reference", sa.String(length=255), nullable=True),
        sa.Column("new_schedule_reference", sa.String(length=255), nullable=True),
        sa.Column("catch_up_amount_reporting_currency", sa.Numeric(20, 6), nullable=False),
        sa.Column("source_contract_reference", sa.String(length=255), nullable=False),
        sa.Column("parent_reference_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_reference_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.Column("supersedes_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["revenue_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["contract_id"], ["revenue_contracts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["supersedes_id"], ["revenue_adjustments.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_revenue_adjustments_run",
        "revenue_adjustments",
        ["tenant_id", "run_id", "effective_date"],
    )
    op.create_index(
        "idx_revenue_adjustments_contract",
        "revenue_adjustments",
        ["tenant_id", "contract_id"],
    )

    revenue_tables = [
        "revenue_runs",
        "revenue_run_events",
        "revenue_contracts",
        "revenue_performance_obligations",
        "revenue_contract_line_items",
        "revenue_schedules",
        "revenue_journal_entries",
        "revenue_adjustments",
    ]

    for table_name in revenue_tables:
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
    for table_name in revenue_tables:
        op.execute(drop_trigger_sql(table_name))
        op.execute(create_trigger_sql(table_name))


def downgrade() -> None:
    revenue_tables = [
        "revenue_adjustments",
        "revenue_journal_entries",
        "revenue_schedules",
        "revenue_contract_line_items",
        "revenue_performance_obligations",
        "revenue_contracts",
        "revenue_run_events",
        "revenue_runs",
    ]

    for table_name in revenue_tables:
        op.execute(drop_trigger_sql(table_name))
        op.drop_table(table_name)
