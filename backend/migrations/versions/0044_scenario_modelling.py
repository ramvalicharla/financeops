"""Scenario modelling tables for set definitions and computed results.

Revision ID: 0044_scenario_modelling
Revises: 0043_forecasting
Create Date: 2026-03-23 10:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from financeops.db.append_only import append_only_function_sql, create_trigger_sql, drop_trigger_sql

revision: str = "0044_scenario_modelling"
down_revision: str | None = "0043_forecasting"
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
    if not _table_exists("scenario_sets"):
        op.create_table(
            "scenario_sets",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False, server_default=sa.text("gen_random_uuid()")),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("base_period", sa.String(length=7), nullable=False),
            sa.Column("horizon_months", sa.Integer(), nullable=False, server_default=sa.text("12")),
            sa.Column("base_forecast_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("forecast_runs.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        )

    if not _table_exists("scenario_definitions"):
        op.create_table(
            "scenario_definitions",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False, server_default=sa.text("gen_random_uuid()")),
            sa.Column("scenario_set_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("scenario_sets.id", ondelete="CASCADE"), nullable=False),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("scenario_name", sa.String(length=100), nullable=False),
            sa.Column("scenario_label", sa.String(length=200), nullable=False),
            sa.Column("is_base_case", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("driver_overrides", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("colour_hex", sa.String(length=7), nullable=False, server_default=sa.text("'#378ADD'")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.CheckConstraint(
                "scenario_name IN ('base','optimistic','pessimistic','custom')",
                name="ck_scenario_definitions_name",
            ),
        )

    if not _table_exists("scenario_results"):
        op.create_table(
            "scenario_results",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False, server_default=sa.text("gen_random_uuid()")),
            sa.Column("scenario_set_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("scenario_sets.id", ondelete="CASCADE"), nullable=False),
            sa.Column("scenario_definition_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("scenario_definitions.id", ondelete="CASCADE"), nullable=False),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        )

    if not _table_exists("scenario_line_items"):
        op.create_table(
            "scenario_line_items",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False, server_default=sa.text("gen_random_uuid()")),
            sa.Column("scenario_result_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("scenario_results.id", ondelete="CASCADE"), nullable=False),
            sa.Column("scenario_set_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("scenario_sets.id", ondelete="CASCADE"), nullable=False),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("period", sa.String(length=7), nullable=False),
            sa.Column("mis_line_item", sa.String(length=300), nullable=False),
            sa.Column("mis_category", sa.String(length=100), nullable=False),
            sa.Column("amount", sa.Numeric(20, 2), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        )

    if not _index_exists("idx_scenario_line_items_result_period_line"):
        op.execute(
            "CREATE INDEX idx_scenario_line_items_result_period_line "
            "ON scenario_line_items (scenario_result_id, period, mis_line_item)"
        )

    for table_name in ("scenario_sets", "scenario_definitions", "scenario_results", "scenario_line_items"):
        if _table_exists(table_name):
            _enable_rls_with_policies(table_name)

    for append_only_table in ("scenario_sets", "scenario_results", "scenario_line_items"):
        if _table_exists(append_only_table):
            op.execute(append_only_function_sql())
            op.execute(drop_trigger_sql(append_only_table))
            op.execute(create_trigger_sql(append_only_table))


def downgrade() -> None:
    for table_name in ("scenario_line_items", "scenario_results", "scenario_sets"):
        if _table_exists(table_name):
            op.execute(drop_trigger_sql(table_name))

    if _index_exists("idx_scenario_line_items_result_period_line") and _table_exists("scenario_line_items"):
        op.drop_index("idx_scenario_line_items_result_period_line", table_name="scenario_line_items")

    if _table_exists("scenario_line_items"):
        op.drop_table("scenario_line_items")
    if _table_exists("scenario_results"):
        op.drop_table("scenario_results")
    if _table_exists("scenario_definitions"):
        op.drop_table("scenario_definitions")
    if _table_exists("scenario_sets"):
        op.drop_table("scenario_sets")

