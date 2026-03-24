"""Tax provision module.

Revision ID: 0060_tax_provision
Revises: 0059_cash_flow_forecast
Create Date: 2026-03-25 00:02:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from financeops.db.append_only import append_only_function_sql, create_trigger_sql, drop_trigger_sql

revision: str = "0060_tax_provision"
down_revision: str | None = "0059_cash_flow_forecast"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    value = bind.execute(sa.text("SELECT to_regclass(:table_name)"), {"table_name": f"public.{table_name}"}).scalar_one_or_none()
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
            f"CREATE POLICY tenant_isolation ON {table_name} USING (tenant_id = {_tenant_expr()})"
        )


def upgrade() -> None:
    if not _table_exists("tax_provision_runs"):
        op.create_table(
            "tax_provision_runs",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("period", sa.String(length=7), nullable=False),
            sa.Column("fiscal_year", sa.Integer(), nullable=False),
            sa.Column("applicable_tax_rate", sa.Numeric(5, 4), nullable=False),
            sa.Column("accounting_profit_before_tax", sa.Numeric(20, 2), nullable=False),
            sa.Column("permanent_differences", sa.Numeric(20, 2), nullable=False, server_default=sa.text("0")),
            sa.Column("timing_differences", sa.Numeric(20, 2), nullable=False, server_default=sa.text("0")),
            sa.Column("taxable_income", sa.Numeric(20, 2), nullable=False),
            sa.Column("current_tax_expense", sa.Numeric(20, 2), nullable=False),
            sa.Column("deferred_tax_asset", sa.Numeric(20, 2), nullable=False, server_default=sa.text("0")),
            sa.Column("deferred_tax_liability", sa.Numeric(20, 2), nullable=False, server_default=sa.text("0")),
            sa.Column("net_deferred_tax", sa.Numeric(20, 2), nullable=False),
            sa.Column("total_tax_expense", sa.Numeric(20, 2), nullable=False),
            sa.Column("effective_tax_rate", sa.Numeric(5, 4), nullable=False),
            sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _table_exists("tax_positions"):
        op.create_table(
            "tax_positions",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("position_name", sa.String(length=200), nullable=False),
            sa.Column("position_type", sa.String(length=30), nullable=False),
            sa.Column("carrying_amount", sa.Numeric(20, 2), nullable=False),
            sa.Column("tax_base", sa.Numeric(20, 2), nullable=False),
            sa.Column("temporary_difference", sa.Numeric(20, 2), nullable=False),
            sa.Column("deferred_tax_impact", sa.Numeric(20, 2), nullable=False),
            sa.Column("is_asset", sa.Boolean(), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _index_exists("idx_tax_provision_runs_tenant_period"):
        op.create_index("idx_tax_provision_runs_tenant_period", "tax_provision_runs", ["tenant_id", "period"], unique=False)

    if not _index_exists("idx_tax_positions_tenant_type"):
        op.create_index("idx_tax_positions_tenant_type", "tax_positions", ["tenant_id", "position_type"], unique=False)

    if _table_exists("tax_provision_runs"):
        op.execute(sa.text(append_only_function_sql()))
        op.execute(sa.text(drop_trigger_sql("tax_provision_runs")))
        op.execute(sa.text(create_trigger_sql("tax_provision_runs")))
        _enable_rls("tax_provision_runs")

    if _table_exists("tax_positions"):
        _enable_rls("tax_positions")


def downgrade() -> None:
    if _table_exists("tax_provision_runs"):
        op.execute(sa.text(drop_trigger_sql("tax_provision_runs")))
    if _table_exists("tax_positions"):
        op.drop_table("tax_positions")
    if _table_exists("tax_provision_runs"):
        op.drop_table("tax_provision_runs")
