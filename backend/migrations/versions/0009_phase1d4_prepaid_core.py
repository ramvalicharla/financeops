"""Phase 1D.4 Prepaid Core

Revision ID: 0009_phase1d4_prepaid_core
Revises: 0008_phase1e_control_plane
Create Date: 2026-03-07 00:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from financeops.db.append_only import append_only_function_sql, create_trigger_sql, drop_trigger_sql

revision: str = "0009_phase1d4_prepaid_core"
down_revision: str | None = "0008_phase1e_control_plane"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "prepaid_runs",
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
        sa.UniqueConstraint("tenant_id", "request_signature", name="uq_prepaid_runs_tenant_signature"),
    )
    op.create_index("idx_prepaid_runs_tenant_created", "prepaid_runs", ["tenant_id", "created_at"])

    op.create_table(
        "prepaid_run_events",
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
        sa.ForeignKeyConstraint(["run_id"], ["prepaid_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "event_seq", name="uq_prepaid_run_events_seq"),
        sa.UniqueConstraint(
            "run_id",
            "event_type",
            "idempotency_key",
            name="uq_prepaid_run_events_idempotent",
        ),
    )
    op.create_index(
        "idx_prepaid_run_events_tenant_run",
        "prepaid_run_events",
        ["tenant_id", "run_id", "event_seq"],
    )

    op.create_table(
        "prepaids",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("prepaid_code", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("prepaid_currency", sa.String(length=3), nullable=False),
        sa.Column("reporting_currency", sa.String(length=3), nullable=False),
        sa.Column("term_start_date", sa.Date(), nullable=False),
        sa.Column("term_end_date", sa.Date(), nullable=False),
        sa.Column("base_amount_contract_currency", sa.Numeric(20, 6), nullable=False),
        sa.Column("period_frequency", sa.String(length=16), nullable=False),
        sa.Column("pattern_type", sa.String(length=32), nullable=False),
        sa.Column("pattern_json_normalized", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("rate_mode", sa.String(length=32), nullable=False),
        sa.Column("source_expense_reference", sa.String(length=255), nullable=False),
        sa.Column("parent_reference_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_reference_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.Column("supersedes_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["supersedes_id"], ["prepaids.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_prepaids_tenant_code", "prepaids", ["tenant_id", "prepaid_code", "created_at"])
    op.create_index(
        "idx_prepaids_tenant_source",
        "prepaids",
        ["tenant_id", "source_expense_reference"],
    )

    op.create_table(
        "prepaid_amortization_schedule",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("prepaid_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("period_seq", sa.Integer(), nullable=False),
        sa.Column("amortization_date", sa.Date(), nullable=False),
        sa.Column("recognition_period_year", sa.Integer(), nullable=False),
        sa.Column("recognition_period_month", sa.Integer(), nullable=False),
        sa.Column("schedule_version_token", sa.String(length=64), nullable=False),
        sa.Column("base_amount_contract_currency", sa.Numeric(20, 6), nullable=False),
        sa.Column("amortized_amount_reporting_currency", sa.Numeric(20, 6), nullable=False),
        sa.Column("cumulative_amortized_reporting_currency", sa.Numeric(20, 6), nullable=False),
        sa.Column("fx_rate_used", sa.Numeric(20, 6), nullable=False),
        sa.Column("fx_rate_date", sa.Date(), nullable=False),
        sa.Column("fx_rate_source", sa.String(length=64), nullable=False),
        sa.Column("schedule_status", sa.String(length=32), nullable=False),
        sa.Column("source_expense_reference", sa.String(length=255), nullable=False),
        sa.Column("parent_reference_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_reference_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["prepaid_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["prepaid_id"], ["prepaids.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id",
            "prepaid_id",
            "amortization_date",
            "schedule_version_token",
            name="uq_prepaid_schedule_date_version",
        ),
        sa.UniqueConstraint(
            "run_id",
            "prepaid_id",
            "period_seq",
            "schedule_version_token",
            name="uq_prepaid_schedule_period_version",
        ),
    )
    op.create_index(
        "idx_prepaid_schedule_tenant_run",
        "prepaid_amortization_schedule",
        ["tenant_id", "run_id", "amortization_date"],
    )
    op.create_index(
        "idx_prepaid_schedule_tenant_prepaid",
        "prepaid_amortization_schedule",
        ["tenant_id", "prepaid_id"],
    )

    op.create_table(
        "prepaid_journal_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("prepaid_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("schedule_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("journal_reference", sa.String(length=128), nullable=False),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("debit_account", sa.String(length=64), nullable=False),
        sa.Column("credit_account", sa.String(length=64), nullable=False),
        sa.Column("amount_reporting_currency", sa.Numeric(20, 6), nullable=False),
        sa.Column("source_expense_reference", sa.String(length=255), nullable=False),
        sa.Column("parent_reference_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_reference_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["prepaid_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["prepaid_id"], ["prepaids.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["schedule_id"], ["prepaid_amortization_schedule.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_prepaid_journal_tenant_run",
        "prepaid_journal_entries",
        ["tenant_id", "run_id", "entry_date"],
    )
    op.create_index(
        "idx_prepaid_journal_tenant_prepaid",
        "prepaid_journal_entries",
        ["tenant_id", "prepaid_id"],
    )

    op.create_table(
        "prepaid_adjustments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("prepaid_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("adjustment_type", sa.String(length=64), nullable=False),
        sa.Column("adjustment_reason", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("prior_schedule_version_token", sa.String(length=64), nullable=False),
        sa.Column("new_schedule_version_token", sa.String(length=64), nullable=False),
        sa.Column("catch_up_amount_reporting_currency", sa.Numeric(20, 6), nullable=False),
        sa.Column("source_expense_reference", sa.String(length=255), nullable=False),
        sa.Column("parent_reference_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_reference_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.Column("supersedes_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["prepaid_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["prepaid_id"], ["prepaids.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["supersedes_id"], ["prepaid_adjustments.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id",
            "prepaid_id",
            "effective_date",
            "adjustment_type",
            "idempotency_key",
            name="uq_prepaid_adjustments_idempotent",
        ),
    )
    op.create_index(
        "idx_prepaid_adjustments_tenant_run",
        "prepaid_adjustments",
        ["tenant_id", "run_id", "effective_date"],
    )
    op.create_index(
        "idx_prepaid_adjustments_tenant_prepaid",
        "prepaid_adjustments",
        ["tenant_id", "prepaid_id"],
    )

    prepaid_tables = [
        "prepaid_runs",
        "prepaid_run_events",
        "prepaids",
        "prepaid_amortization_schedule",
        "prepaid_journal_entries",
        "prepaid_adjustments",
    ]

    for table_name in prepaid_tables:
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
    for table_name in prepaid_tables:
        op.execute(drop_trigger_sql(table_name))
        op.execute(create_trigger_sql(table_name))


def downgrade() -> None:
    prepaid_tables = [
        "prepaid_adjustments",
        "prepaid_journal_entries",
        "prepaid_amortization_schedule",
        "prepaids",
        "prepaid_run_events",
        "prepaid_runs",
    ]

    for table_name in prepaid_tables:
        op.execute(drop_trigger_sql(table_name))
        op.drop_table(table_name)
