"""Phase 1B FX Rate Engine tables

Revision ID: 0004_phase1b_fx
Revises: 0003_phase1a
Create Date: 2026-03-06 00:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from financeops.db.append_only import (
    append_only_function_sql,
    create_trigger_sql,
    drop_trigger_sql,
)

revision: str = "0004_phase1b_fx"
down_revision: str | None = "0003_phase1a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "fx_rate_fetch_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(64), nullable=False),
        sa.Column("previous_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rate_date", sa.Date(), nullable=False),
        sa.Column("base_currency", sa.String(3), nullable=False),
        sa.Column("quote_currency", sa.String(3), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("provider_count", sa.Integer(), nullable=False),
        sa.Column("success_count", sa.Integer(), nullable=False),
        sa.Column("failure_count", sa.Integer(), nullable=False),
        sa.Column("selected_rate", sa.Numeric(20, 6), nullable=True),
        sa.Column("selected_source", sa.String(64), nullable=True),
        sa.Column("selection_method", sa.String(128), nullable=True),
        sa.Column("fallback_used", sa.Boolean(), nullable=False),
        sa.Column("initiated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.Column("provider_errors", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_fx_fetch_runs_tenant_pair_date",
        "fx_rate_fetch_runs",
        ["tenant_id", "base_currency", "quote_currency", "rate_date"],
    )
    op.create_index(
        "idx_fx_fetch_runs_tenant_created",
        "fx_rate_fetch_runs",
        ["tenant_id", "created_at"],
    )

    op.create_table(
        "fx_rate_quotes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(64), nullable=False),
        sa.Column("previous_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fetch_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider_name", sa.String(64), nullable=False),
        sa.Column("rate_date", sa.Date(), nullable=False),
        sa.Column("base_currency", sa.String(3), nullable=False),
        sa.Column("quote_currency", sa.String(3), nullable=False),
        sa.Column("rate", sa.Numeric(20, 6), nullable=False),
        sa.Column("source_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(
            ["fetch_run_id"], ["fx_rate_fetch_runs.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_fx_quotes_tenant_pair_date_provider",
        "fx_rate_quotes",
        ["tenant_id", "base_currency", "quote_currency", "rate_date", "provider_name"],
    )
    op.create_index(
        "idx_fx_quotes_fetch_run",
        "fx_rate_quotes",
        ["tenant_id", "fetch_run_id"],
    )

    op.create_table(
        "fx_manual_monthly_rates",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(64), nullable=False),
        sa.Column("previous_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_year", sa.Integer(), nullable=False),
        sa.Column("period_month", sa.Integer(), nullable=False),
        sa.Column("base_currency", sa.String(3), nullable=False),
        sa.Column("quote_currency", sa.String(3), nullable=False),
        sa.Column("rate", sa.Numeric(20, 6), nullable=False),
        sa.Column("entered_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("supersedes_rate_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("is_month_end_locked", sa.Boolean(), nullable=False),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.ForeignKeyConstraint(
            ["supersedes_rate_id"], ["fx_manual_monthly_rates.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_fx_manual_tenant_period_pair",
        "fx_manual_monthly_rates",
        ["tenant_id", "period_year", "period_month", "base_currency", "quote_currency"],
    )
    op.create_index(
        "idx_fx_manual_tenant_created",
        "fx_manual_monthly_rates",
        ["tenant_id", "created_at"],
    )

    op.create_table(
        "fx_variance_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(64), nullable=False),
        sa.Column("previous_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_year", sa.Integer(), nullable=False),
        sa.Column("period_month", sa.Integer(), nullable=False),
        sa.Column("entity_name", sa.String(255), nullable=True),
        sa.Column("base_currency", sa.String(3), nullable=False),
        sa.Column("quote_currency", sa.String(3), nullable=False),
        sa.Column("expected_difference", sa.Numeric(20, 6), nullable=False),
        sa.Column("actual_difference", sa.Numeric(20, 6), nullable=False),
        sa.Column("fx_variance", sa.Numeric(20, 6), nullable=False),
        sa.Column("computed_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_fx_variance_tenant_period_pair",
        "fx_variance_results",
        ["tenant_id", "period_year", "period_month", "base_currency", "quote_currency"],
    )
    op.create_index(
        "idx_fx_variance_tenant_created",
        "fx_variance_results",
        ["tenant_id", "created_at"],
    )

    fx_tables = [
        "fx_rate_fetch_runs",
        "fx_rate_quotes",
        "fx_manual_monthly_rates",
        "fx_variance_results",
    ]
    for table in fx_tables:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY {table}_tenant_isolation
              ON {table}
              USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
            """
        )

    op.execute(append_only_function_sql())
    for table in fx_tables:
        op.execute(drop_trigger_sql(table))
        op.execute(create_trigger_sql(table))


def downgrade() -> None:
    fx_tables = [
        "fx_variance_results",
        "fx_manual_monthly_rates",
        "fx_rate_quotes",
        "fx_rate_fetch_runs",
    ]
    for table in fx_tables:
        op.execute(drop_trigger_sql(table))
        op.drop_table(table)
