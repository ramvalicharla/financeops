"""Budgeting module tables for annual versions and line items.

Revision ID: 0042_budgeting
Revises: 0041_expense_management
Create Date: 2026-03-23 08:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from financeops.db.append_only import append_only_function_sql, create_trigger_sql, drop_trigger_sql

revision: str = "0042_budgeting"
down_revision: str | None = "0041_expense_management"
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
    if not _table_exists("budget_versions"):
        op.create_table(
            "budget_versions",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False, server_default=sa.text("gen_random_uuid()")),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("fiscal_year", sa.Integer(), nullable=False),
            sa.Column("version_name", sa.String(length=100), nullable=False),
            sa.Column("version_number", sa.Integer(), nullable=False, server_default=sa.text("1")),
            sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'draft'")),
            sa.Column("is_board_approved", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("board_approved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("board_approved_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("iam_users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("iam_users.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.CheckConstraint("status IN ('draft','submitted','approved','superseded')", name="ck_budget_versions_status"),
            sa.UniqueConstraint("tenant_id", "fiscal_year", "version_number", name="uq_budget_versions_tenant_year_version"),
        )

    if not _table_exists("budget_line_items"):
        op.create_table(
            "budget_line_items",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False, server_default=sa.text("gen_random_uuid()")),
            sa.Column("budget_version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("budget_versions.id", ondelete="CASCADE"), nullable=False),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("mis_line_item", sa.String(length=300), nullable=False),
            sa.Column("mis_category", sa.String(length=100), nullable=False),
            sa.Column("month_01", sa.Numeric(20, 2), nullable=False, server_default=sa.text("0")),
            sa.Column("month_02", sa.Numeric(20, 2), nullable=False, server_default=sa.text("0")),
            sa.Column("month_03", sa.Numeric(20, 2), nullable=False, server_default=sa.text("0")),
            sa.Column("month_04", sa.Numeric(20, 2), nullable=False, server_default=sa.text("0")),
            sa.Column("month_05", sa.Numeric(20, 2), nullable=False, server_default=sa.text("0")),
            sa.Column("month_06", sa.Numeric(20, 2), nullable=False, server_default=sa.text("0")),
            sa.Column("month_07", sa.Numeric(20, 2), nullable=False, server_default=sa.text("0")),
            sa.Column("month_08", sa.Numeric(20, 2), nullable=False, server_default=sa.text("0")),
            sa.Column("month_09", sa.Numeric(20, 2), nullable=False, server_default=sa.text("0")),
            sa.Column("month_10", sa.Numeric(20, 2), nullable=False, server_default=sa.text("0")),
            sa.Column("month_11", sa.Numeric(20, 2), nullable=False, server_default=sa.text("0")),
            sa.Column("month_12", sa.Numeric(20, 2), nullable=False, server_default=sa.text("0")),
            sa.Column(
                "annual_total",
                sa.Numeric(20, 2),
                sa.Computed(
                    "month_01 + month_02 + month_03 + month_04 + "
                    "month_05 + month_06 + month_07 + month_08 + "
                    "month_09 + month_10 + month_11 + month_12",
                    persisted=True,
                ),
                nullable=False,
            ),
            sa.Column("basis", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        )

    if not _index_exists("idx_budget_versions_tenant_year"):
        op.execute("CREATE INDEX idx_budget_versions_tenant_year ON budget_versions (tenant_id, fiscal_year)")
    if not _index_exists("idx_budget_line_items_version_line"):
        op.execute("CREATE INDEX idx_budget_line_items_version_line ON budget_line_items (budget_version_id, mis_line_item)")
    if not _index_exists("idx_budget_line_items_tenant_version"):
        op.execute("CREATE INDEX idx_budget_line_items_tenant_version ON budget_line_items (tenant_id, budget_version_id)")

    for table_name in ("budget_versions", "budget_line_items"):
        if _table_exists(table_name):
            _enable_rls_with_policies(table_name)

    if _table_exists("budget_line_items"):
        op.execute(append_only_function_sql())
        op.execute(drop_trigger_sql("budget_line_items"))
        op.execute(create_trigger_sql("budget_line_items"))


def downgrade() -> None:
    if _table_exists("budget_line_items"):
        op.execute(drop_trigger_sql("budget_line_items"))

    if _index_exists("idx_budget_line_items_tenant_version") and _table_exists("budget_line_items"):
        op.drop_index("idx_budget_line_items_tenant_version", table_name="budget_line_items")
    if _index_exists("idx_budget_line_items_version_line") and _table_exists("budget_line_items"):
        op.drop_index("idx_budget_line_items_version_line", table_name="budget_line_items")
    if _index_exists("idx_budget_versions_tenant_year") and _table_exists("budget_versions"):
        op.drop_index("idx_budget_versions_tenant_year", table_name="budget_versions")

    if _table_exists("budget_line_items"):
        op.drop_table("budget_line_items")
    if _table_exists("budget_versions"):
        op.drop_table("budget_versions")
