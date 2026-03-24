"""Debt covenants module.

Revision ID: 0061_debt_covenants
Revises: 0060_tax_provision
Create Date: 2026-03-25 00:05:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from financeops.db.append_only import append_only_function_sql, create_trigger_sql, drop_trigger_sql

revision: str = "0061_debt_covenants"
down_revision: str | None = "0060_tax_provision"
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
    if not _table_exists("covenant_definitions"):
        op.create_table(
            "covenant_definitions",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("facility_name", sa.String(length=200), nullable=False),
            sa.Column("lender_name", sa.String(length=200), nullable=False),
            sa.Column("covenant_type", sa.String(length=50), nullable=False),
            sa.Column("covenant_label", sa.String(length=200), nullable=False),
            sa.Column("threshold_value", sa.Numeric(20, 6), nullable=False),
            sa.Column("threshold_direction", sa.String(length=10), nullable=False),
            sa.Column("measurement_frequency", sa.String(length=20), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("grace_period_days", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("notification_threshold_pct", sa.Numeric(5, 2), nullable=False, server_default=sa.text("90")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _table_exists("covenant_breach_events"):
        op.create_table(
            "covenant_breach_events",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
            sa.Column("covenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("period", sa.String(length=7), nullable=False),
            sa.Column("actual_value", sa.Numeric(20, 6), nullable=False),
            sa.Column("threshold_value", sa.Numeric(20, 6), nullable=False),
            sa.Column("breach_type", sa.String(length=20), nullable=False),
            sa.Column("variance_pct", sa.Numeric(8, 4), nullable=False),
            sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.ForeignKeyConstraint(["covenant_id"], ["covenant_definitions.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _index_exists("idx_covenant_breach_events_covenant_period"):
        op.create_index("idx_covenant_breach_events_covenant_period", "covenant_breach_events", ["covenant_id", "period"], unique=False)
    if not _index_exists("idx_covenant_breach_events_tenant_type_created"):
        op.create_index("idx_covenant_breach_events_tenant_type_created", "covenant_breach_events", ["tenant_id", "breach_type", "computed_at"], unique=False)

    if _table_exists("covenant_breach_events"):
        op.execute(sa.text(append_only_function_sql()))
        op.execute(sa.text(drop_trigger_sql("covenant_breach_events")))
        op.execute(sa.text(create_trigger_sql("covenant_breach_events")))

    if _table_exists("covenant_definitions"):
        _enable_rls("covenant_definitions")
    if _table_exists("covenant_breach_events"):
        _enable_rls("covenant_breach_events")


def downgrade() -> None:
    if _table_exists("covenant_breach_events"):
        op.execute(sa.text(drop_trigger_sql("covenant_breach_events")))
    if _table_exists("covenant_breach_events"):
        op.drop_table("covenant_breach_events")
    if _table_exists("covenant_definitions"):
        op.drop_table("covenant_definitions")
