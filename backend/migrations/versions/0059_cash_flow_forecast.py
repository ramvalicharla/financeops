"""Cash flow forecast module.

Revision ID: 0059_cash_flow_forecast
Revises: 0058_search_index
Create Date: 2026-03-24 23:58:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from financeops.db.append_only import append_only_function_sql, create_trigger_sql, drop_trigger_sql

revision: str = "0059_cash_flow_forecast"
down_revision: str | None = "0058_search_index"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    value = bind.execute(
        sa.text("SELECT to_regclass(:table_name)"),
        {"table_name": f"public.{table_name}"},
    ).scalar_one_or_none()
    return value is not None


def _index_exists(index_name: str) -> bool:
    bind = op.get_bind()
    value = bind.execute(
        sa.text(
            """
            SELECT 1
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE c.relkind = 'i'
              AND n.nspname = 'public'
              AND c.relname = :index_name
            LIMIT 1
            """
        ),
        {"index_name": index_name},
    ).scalar_one_or_none()
    return value is not None


def _policy_exists(table_name: str, policy_name: str) -> bool:
    bind = op.get_bind()
    value = bind.execute(
        sa.text(
            """
            SELECT 1
            FROM pg_policies
            WHERE schemaname = 'public'
              AND tablename = :table_name
              AND policyname = :policy_name
            LIMIT 1
            """
        ),
        {"table_name": table_name, "policy_name": policy_name},
    ).scalar_one_or_none()
    return value is not None


def _tenant_expr() -> str:
    return (
        "COALESCE(NULLIF(current_setting('app.tenant_id', true), ''), "
        "NULLIF(current_setting('app.current_tenant_id', true), ''))::uuid"
    )


def _enable_rls(table_name: str) -> None:
    op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
    if not _policy_exists(table_name, "tenant_isolation"):
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table_name} "
            f"USING (tenant_id = {_tenant_expr()})"
        )


def upgrade() -> None:
    if not _table_exists("cash_flow_forecast_runs"):
        op.create_table(
            "cash_flow_forecast_runs",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("run_name", sa.String(length=200), nullable=False),
            sa.Column("base_date", sa.Date(), nullable=False),
            sa.Column("weeks", sa.Integer(), nullable=False, server_default=sa.text("13")),
            sa.Column("opening_cash_balance", sa.Numeric(20, 2), nullable=False),
            sa.Column("currency", sa.String(length=3), nullable=False, server_default=sa.text("'INR'")),
            sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'draft'")),
            sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _table_exists("cash_flow_forecast_assumptions"):
        op.create_table(
            "cash_flow_forecast_assumptions",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
            sa.Column("forecast_run_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("week_number", sa.Integer(), nullable=False),
            sa.Column("week_start_date", sa.Date(), nullable=False),
            sa.Column("customer_collections", sa.Numeric(20, 2), nullable=False, server_default=sa.text("0")),
            sa.Column("other_inflows", sa.Numeric(20, 2), nullable=False, server_default=sa.text("0")),
            sa.Column("supplier_payments", sa.Numeric(20, 2), nullable=False, server_default=sa.text("0")),
            sa.Column("payroll", sa.Numeric(20, 2), nullable=False, server_default=sa.text("0")),
            sa.Column("rent_and_utilities", sa.Numeric(20, 2), nullable=False, server_default=sa.text("0")),
            sa.Column("loan_repayments", sa.Numeric(20, 2), nullable=False, server_default=sa.text("0")),
            sa.Column("tax_payments", sa.Numeric(20, 2), nullable=False, server_default=sa.text("0")),
            sa.Column("capex", sa.Numeric(20, 2), nullable=False, server_default=sa.text("0")),
            sa.Column("other_outflows", sa.Numeric(20, 2), nullable=False, server_default=sa.text("0")),
            sa.Column("total_inflows", sa.Numeric(20, 2), nullable=False, server_default=sa.text("0")),
            sa.Column("total_outflows", sa.Numeric(20, 2), nullable=False, server_default=sa.text("0")),
            sa.Column("net_cash_flow", sa.Numeric(20, 2), nullable=False, server_default=sa.text("0")),
            sa.Column("closing_balance", sa.Numeric(20, 2), nullable=False, server_default=sa.text("0")),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.ForeignKeyConstraint(["forecast_run_id"], ["cash_flow_forecast_runs.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("forecast_run_id", "week_number", name="uq_cash_flow_forecast_assumptions_run_week"),
        )

    if not _index_exists("idx_cash_flow_forecast_runs_tenant_base_date"):
        op.create_index(
            "idx_cash_flow_forecast_runs_tenant_base_date",
            "cash_flow_forecast_runs",
            ["tenant_id", "base_date"],
            unique=False,
        )

    if not _index_exists("idx_cash_flow_forecast_assumptions_run_week"):
        op.create_index(
            "idx_cash_flow_forecast_assumptions_run_week",
            "cash_flow_forecast_assumptions",
            ["forecast_run_id", "week_number"],
            unique=False,
        )

    if _table_exists("cash_flow_forecast_runs"):
        op.execute(sa.text(append_only_function_sql()))
        op.execute(sa.text(drop_trigger_sql("cash_flow_forecast_runs")))
        op.execute(sa.text(create_trigger_sql("cash_flow_forecast_runs")))
        _enable_rls("cash_flow_forecast_runs")

    if _table_exists("cash_flow_forecast_assumptions"):
        _enable_rls("cash_flow_forecast_assumptions")


def downgrade() -> None:
    if _table_exists("cash_flow_forecast_runs"):
        op.execute(sa.text(drop_trigger_sql("cash_flow_forecast_runs")))
    if _table_exists("cash_flow_forecast_assumptions"):
        op.drop_table("cash_flow_forecast_assumptions")
    if _table_exists("cash_flow_forecast_runs"):
        op.drop_table("cash_flow_forecast_runs")
