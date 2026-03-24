"""Multi GAAP module.

Revision ID: 0065_multi_gaap
Revises: 0064_statutory_registers
Create Date: 2026-03-25 00:19:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from financeops.db.append_only import append_only_function_sql, create_trigger_sql, drop_trigger_sql

revision: str = "0065_multi_gaap"
down_revision: str | None = "0064_statutory_registers"
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
        op.execute(f"CREATE POLICY tenant_isolation ON {table_name} USING (tenant_id = {_tenant_expr()})")


def upgrade() -> None:
    if not _table_exists("multi_gaap_configs"):
        op.create_table(
            "multi_gaap_configs",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("primary_gaap", sa.String(length=20), nullable=False, server_default=sa.text("'INDAS'")),
            sa.Column("secondary_gaaps", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
            sa.Column("revenue_recognition_policy", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("lease_classification_policy", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("financial_instruments_policy", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("tenant_id"),
        )

    if not _table_exists("multi_gaap_runs"):
        op.create_table(
            "multi_gaap_runs",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("period", sa.String(length=7), nullable=False),
            sa.Column("gaap_framework", sa.String(length=20), nullable=False),
            sa.Column("revenue", sa.Numeric(20, 2), nullable=False),
            sa.Column("gross_profit", sa.Numeric(20, 2), nullable=False),
            sa.Column("ebitda", sa.Numeric(20, 2), nullable=False),
            sa.Column("ebit", sa.Numeric(20, 2), nullable=False),
            sa.Column("profit_before_tax", sa.Numeric(20, 2), nullable=False),
            sa.Column("profit_after_tax", sa.Numeric(20, 2), nullable=False),
            sa.Column("total_assets", sa.Numeric(20, 2), nullable=False),
            sa.Column("total_equity", sa.Numeric(20, 2), nullable=False),
            sa.Column("adjustments", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
            sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("tenant_id", "period", "gaap_framework", name="uq_multi_gaap_runs_tenant_period_framework"),
        )

    if not _index_exists("idx_multi_gaap_runs_tenant_period_framework"):
        op.create_index("idx_multi_gaap_runs_tenant_period_framework", "multi_gaap_runs", ["tenant_id", "period", "gaap_framework"], unique=False)

    if _table_exists("multi_gaap_runs"):
        op.execute(sa.text(append_only_function_sql()))
        op.execute(sa.text(drop_trigger_sql("multi_gaap_runs")))
        op.execute(sa.text(create_trigger_sql("multi_gaap_runs")))

    if _table_exists("multi_gaap_configs"):
        _enable_rls("multi_gaap_configs")
    if _table_exists("multi_gaap_runs"):
        _enable_rls("multi_gaap_runs")


def downgrade() -> None:
    if _table_exists("multi_gaap_runs"):
        op.execute(sa.text(drop_trigger_sql("multi_gaap_runs")))
    if _table_exists("multi_gaap_runs"):
        op.drop_table("multi_gaap_runs")
    if _table_exists("multi_gaap_configs"):
        op.drop_table("multi_gaap_configs")
