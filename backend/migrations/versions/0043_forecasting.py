"""Forecasting module tables for runs, assumptions, and line items.

Revision ID: 0043_forecasting
Revises: 0042_budgeting
Create Date: 2026-03-23 09:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from financeops.db.append_only import append_only_function_sql, create_trigger_sql, drop_trigger_sql

revision: str = "0043_forecasting"
down_revision: str | None = "0042_budgeting"
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


def _enable_rls_with_policies(table_name: str) -> None:
    op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
    if not _policy_exists(table_name, "tenant_isolation"):
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table_name} "
            "USING (tenant_id = COALESCE(NULLIF(current_setting('app.tenant_id', true), ''), NULLIF(current_setting('app.current_tenant_id', true), ''))::uuid)"
        )


def upgrade() -> None:
    if not _table_exists("forecast_runs"):
        op.create_table(
            "forecast_runs",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False, server_default=sa.text("gen_random_uuid()")),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("run_name", sa.String(length=200), nullable=False),
            sa.Column("forecast_type", sa.String(length=20), nullable=False),
            sa.Column("base_period", sa.String(length=7), nullable=False),
            sa.Column("horizon_months", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'draft'")),
            sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("published_by", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.CheckConstraint("forecast_type IN ('rolling_12','annual','quarterly')", name="ck_forecast_runs_type"),
            sa.CheckConstraint("status IN ('draft','published','superseded')", name="ck_forecast_runs_status"),
        )

    if not _table_exists("forecast_assumptions"):
        op.create_table(
            "forecast_assumptions",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False, server_default=sa.text("gen_random_uuid()")),
            sa.Column("forecast_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("forecast_runs.id", ondelete="CASCADE"), nullable=False),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("assumption_key", sa.String(length=100), nullable=False),
            sa.Column("assumption_value", sa.Numeric(20, 6), nullable=False),
            sa.Column("assumption_label", sa.String(length=200), nullable=False),
            sa.Column("category", sa.String(length=50), nullable=False),
            sa.Column("basis", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.CheckConstraint(
                "category IN ('growth','margins','headcount','fx','capex','other')",
                name="ck_forecast_assumptions_category",
            ),
            sa.UniqueConstraint("forecast_run_id", "assumption_key", name="uq_forecast_assumptions_run_key"),
        )

    if not _table_exists("forecast_line_items"):
        op.create_table(
            "forecast_line_items",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False, server_default=sa.text("gen_random_uuid()")),
            sa.Column("forecast_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("forecast_runs.id", ondelete="CASCADE"), nullable=False),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("period", sa.String(length=7), nullable=False),
            sa.Column("is_actual", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("mis_line_item", sa.String(length=300), nullable=False),
            sa.Column("mis_category", sa.String(length=100), nullable=False),
            sa.Column("amount", sa.Numeric(20, 2), nullable=False),
            sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        )

    if not _index_exists("idx_forecast_line_items_run_period_line"):
        op.execute(
            "CREATE INDEX idx_forecast_line_items_run_period_line "
            "ON forecast_line_items (forecast_run_id, period, mis_line_item)"
        )
    if not _index_exists("idx_forecast_line_items_tenant_period"):
        op.execute("CREATE INDEX idx_forecast_line_items_tenant_period ON forecast_line_items (tenant_id, period)")

    for table_name in ("forecast_runs", "forecast_assumptions", "forecast_line_items"):
        if _table_exists(table_name):
            _enable_rls_with_policies(table_name)

    for append_only_table in ("forecast_runs", "forecast_line_items"):
        if _table_exists(append_only_table):
            op.execute(append_only_function_sql())
            op.execute(drop_trigger_sql(append_only_table))
            op.execute(create_trigger_sql(append_only_table))


def downgrade() -> None:
    for table_name in ("forecast_line_items", "forecast_runs"):
        if _table_exists(table_name):
            op.execute(drop_trigger_sql(table_name))

    if _index_exists("idx_forecast_line_items_tenant_period") and _table_exists("forecast_line_items"):
        op.drop_index("idx_forecast_line_items_tenant_period", table_name="forecast_line_items")
    if _index_exists("idx_forecast_line_items_run_period_line") and _table_exists("forecast_line_items"):
        op.drop_index("idx_forecast_line_items_run_period_line", table_name="forecast_line_items")

    if _table_exists("forecast_line_items"):
        op.drop_table("forecast_line_items")
    if _table_exists("forecast_assumptions"):
        op.drop_table("forecast_assumptions")
    if _table_exists("forecast_runs"):
        op.drop_table("forecast_runs")

