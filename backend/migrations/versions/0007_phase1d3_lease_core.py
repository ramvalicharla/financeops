"""Phase 1D.3 Lease Accounting Core

Revision ID: 0007_phase1d3_lease_core
Revises: 0006_phase1d2_revenue_core
Create Date: 2026-03-07 00:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from financeops.db.append_only import append_only_function_sql, create_trigger_sql, drop_trigger_sql

revision: str = "0007_phase1d3_lease_core"
down_revision: str | None = "0006_phase1d2_revenue_core"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "lease_runs",
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
        sa.UniqueConstraint("tenant_id", "request_signature", name="uq_lease_runs_tenant_signature"),
    )
    op.create_index("idx_lease_runs_tenant_created", "lease_runs", ["tenant_id", "created_at"])

    op.create_table(
        "lease_run_events",
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
        sa.ForeignKeyConstraint(["run_id"], ["lease_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "event_seq", name="uq_lease_run_events_seq"),
        sa.UniqueConstraint("run_id", "event_type", "idempotency_key", name="uq_lease_run_events_idempotent"),
    )
    op.create_index(
        "idx_lease_run_events_tenant_run",
        "lease_run_events",
        ["tenant_id", "run_id", "event_seq"],
    )

    op.create_table(
        "leases",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_number", sa.String(length=128), nullable=False),
        sa.Column("counterparty_id", sa.String(length=128), nullable=False),
        sa.Column("lease_currency", sa.String(length=3), nullable=False),
        sa.Column("commencement_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("payment_frequency", sa.String(length=32), nullable=False),
        sa.Column("initial_discount_rate", sa.Numeric(20, 6), nullable=False),
        sa.Column("discount_rate_source", sa.String(length=64), nullable=False),
        sa.Column("discount_rate_reference_date", sa.Date(), nullable=False),
        sa.Column("discount_rate_policy_code", sa.String(length=64), nullable=False),
        sa.Column("initial_measurement_basis", sa.String(length=64), nullable=False),
        sa.Column("source_lease_reference", sa.String(length=255), nullable=False),
        sa.Column("policy_code", sa.String(length=64), nullable=False),
        sa.Column("policy_version", sa.String(length=64), nullable=False),
        sa.Column("parent_reference_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_reference_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.Column("supersedes_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["supersedes_id"], ["leases.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_leases_tenant_number", "leases", ["tenant_id", "lease_number", "created_at"])
    op.create_index("idx_leases_tenant_source", "leases", ["tenant_id", "source_lease_reference"])

    op.create_table(
        "lease_payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payment_date", sa.Date(), nullable=False),
        sa.Column("payment_amount_lease_currency", sa.Numeric(20, 6), nullable=False),
        sa.Column("payment_type", sa.String(length=64), nullable=False),
        sa.Column("payment_sequence", sa.Integer(), nullable=False),
        sa.Column("source_lease_reference", sa.String(length=255), nullable=False),
        sa.Column("parent_reference_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_reference_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.Column("supersedes_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["lease_id"], ["leases.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["supersedes_id"], ["lease_payments.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "lease_id", "payment_sequence", name="uq_lease_payments_sequence"),
    )
    op.create_index("idx_lease_payments_lease", "lease_payments", ["tenant_id", "lease_id", "payment_sequence"])

    op.create_table(
        "lease_liability_schedule",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("lease_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payment_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("schedule_date", sa.Date(), nullable=False),
        sa.Column("period_year", sa.Integer(), nullable=False),
        sa.Column("period_month", sa.Integer(), nullable=False),
        sa.Column("opening_liability_reporting_currency", sa.Numeric(20, 6), nullable=False),
        sa.Column("interest_expense_reporting_currency", sa.Numeric(20, 6), nullable=False),
        sa.Column("payment_amount_reporting_currency", sa.Numeric(20, 6), nullable=False),
        sa.Column("closing_liability_reporting_currency", sa.Numeric(20, 6), nullable=False),
        sa.Column("fx_rate_used", sa.Numeric(20, 6), nullable=False),
        sa.Column("source_lease_reference", sa.String(length=255), nullable=False),
        sa.Column("parent_reference_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_reference_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["lease_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["lease_id"], ["leases.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["payment_id"], ["lease_payments.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "lease_id", "schedule_date", name="uq_lease_liability_schedule_natural"),
    )
    op.create_index(
        "idx_lease_liability_schedule_run",
        "lease_liability_schedule",
        ["tenant_id", "run_id", "schedule_date"],
    )

    op.create_table(
        "lease_rou_schedule",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("lease_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("schedule_date", sa.Date(), nullable=False),
        sa.Column("period_year", sa.Integer(), nullable=False),
        sa.Column("period_month", sa.Integer(), nullable=False),
        sa.Column("opening_rou_reporting_currency", sa.Numeric(20, 6), nullable=False),
        sa.Column("amortization_expense_reporting_currency", sa.Numeric(20, 6), nullable=False),
        sa.Column("impairment_amount_reporting_currency", sa.Numeric(20, 6), nullable=False),
        sa.Column("closing_rou_reporting_currency", sa.Numeric(20, 6), nullable=False),
        sa.Column("fx_rate_used", sa.Numeric(20, 6), nullable=False),
        sa.Column("source_lease_reference", sa.String(length=255), nullable=False),
        sa.Column("parent_reference_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_reference_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["lease_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["lease_id"], ["leases.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "lease_id", "schedule_date", name="uq_lease_rou_schedule_natural"),
    )
    op.create_index("idx_lease_rou_schedule_run", "lease_rou_schedule", ["tenant_id", "run_id", "schedule_date"])

    op.create_table(
        "lease_modifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("lease_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("modification_type", sa.String(length=64), nullable=False),
        sa.Column("modification_reason", sa.Text(), nullable=False),
        sa.Column("prior_schedule_reference", sa.String(length=255), nullable=True),
        sa.Column("new_schedule_reference", sa.String(length=255), nullable=True),
        sa.Column("remeasurement_delta_reporting_currency", sa.Numeric(20, 6), nullable=False),
        sa.Column("source_lease_reference", sa.String(length=255), nullable=False),
        sa.Column("parent_reference_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_reference_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.Column("supersedes_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["lease_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["lease_id"], ["leases.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["supersedes_id"], ["lease_modifications.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_lease_modifications_run", "lease_modifications", ["tenant_id", "run_id", "effective_date"])
    op.create_index("idx_lease_modifications_lease", "lease_modifications", ["tenant_id", "lease_id"])

    op.create_table(
        "lease_journal_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("lease_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("liability_schedule_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("rou_schedule_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("journal_reference", sa.String(length=128), nullable=False),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("debit_account", sa.String(length=64), nullable=False),
        sa.Column("credit_account", sa.String(length=64), nullable=False),
        sa.Column("amount_reporting_currency", sa.Numeric(20, 6), nullable=False),
        sa.Column("source_lease_reference", sa.String(length=255), nullable=False),
        sa.Column("parent_reference_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_reference_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["lease_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["lease_id"], ["leases.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["liability_schedule_id"], ["lease_liability_schedule.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["rou_schedule_id"], ["lease_rou_schedule.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_lease_journal_run", "lease_journal_entries", ["tenant_id", "run_id", "entry_date"])
    op.create_index("idx_lease_journal_lease", "lease_journal_entries", ["tenant_id", "lease_id"])

    lease_tables = [
        "lease_runs",
        "lease_run_events",
        "leases",
        "lease_payments",
        "lease_liability_schedule",
        "lease_rou_schedule",
        "lease_modifications",
        "lease_journal_entries",
    ]

    for table_name in lease_tables:
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
    for table_name in lease_tables:
        op.execute(drop_trigger_sql(table_name))
        op.execute(create_trigger_sql(table_name))


def downgrade() -> None:
    lease_tables = [
        "lease_journal_entries",
        "lease_modifications",
        "lease_rou_schedule",
        "lease_liability_schedule",
        "lease_payments",
        "leases",
        "lease_run_events",
        "lease_runs",
    ]

    for table_name in lease_tables:
        op.execute(drop_trigger_sql(table_name))
        op.drop_table(table_name)
