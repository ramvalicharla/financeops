"""AI cost ledger for per-tenant token budget tracking and immutable AI spend audit trail.

Revision ID: 0038_ai_cost_ledger
Revises: 0037_gdpr_erasure
Create Date: 2026-03-22 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from financeops.db.append_only import append_only_function_sql, create_trigger_sql, drop_trigger_sql

revision: str = "0038_ai_cost_ledger"
down_revision: str | None = "0037_gdpr_erasure"
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
    if not _table_exists("ai_cost_events"):
        op.create_table(
            "ai_cost_events",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                nullable=False,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column(
                "tenant_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("iam_tenants.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("task_type", sa.String(length=50), nullable=False),
            sa.Column("provider", sa.String(length=30), nullable=False),
            sa.Column("model", sa.String(length=100), nullable=False),
            sa.Column("prompt_tokens", sa.Integer(), nullable=False),
            sa.Column("completion_tokens", sa.Integer(), nullable=False),
            sa.Column("total_tokens", sa.Integer(), nullable=False),
            sa.Column("cost_usd", sa.Numeric(10, 6), nullable=False),
            sa.Column(
                "was_cached",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column(
                "was_fallback",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column(
                "pii_was_masked",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column("pipeline_run_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
        )

    if not _table_exists("tenant_token_budgets"):
        op.create_table(
            "tenant_token_budgets",
            sa.Column(
                "tenant_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("iam_tenants.id", ondelete="CASCADE"),
                primary_key=True,
                nullable=False,
            ),
            sa.Column(
                "monthly_token_limit",
                sa.BigInteger(),
                nullable=False,
                server_default=sa.text("1000000"),
            ),
            sa.Column(
                "monthly_cost_limit_usd",
                sa.Numeric(10, 2),
                nullable=False,
                server_default=sa.text("50.00"),
            ),
            sa.Column(
                "current_month_tokens",
                sa.BigInteger(),
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.Column(
                "current_month_cost_usd",
                sa.Numeric(10, 6),
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.Column("budget_period_start", sa.Date(), nullable=False),
            sa.Column(
                "alert_threshold_pct",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("80"),
            ),
            sa.Column(
                "hard_stop_on_budget",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
        )

    if not _index_exists("idx_ai_cost_events_tenant_created"):
        op.execute(
            "CREATE INDEX idx_ai_cost_events_tenant_created "
            "ON ai_cost_events (tenant_id, created_at DESC)"
        )

    if not _index_exists("idx_tenant_token_budgets_period"):
        op.execute(
            "CREATE INDEX idx_tenant_token_budgets_period "
            "ON tenant_token_budgets (budget_period_start)"
        )

    if _table_exists("ai_cost_events"):
        _enable_rls_with_policies("ai_cost_events")
        op.execute(append_only_function_sql())
        op.execute(drop_trigger_sql("ai_cost_events"))
        op.execute(create_trigger_sql("ai_cost_events"))
    if _table_exists("tenant_token_budgets"):
        _enable_rls_with_policies("tenant_token_budgets")


def downgrade() -> None:
    if _table_exists("ai_cost_events"):
        op.execute(drop_trigger_sql("ai_cost_events"))
        if _index_exists("idx_ai_cost_events_tenant_created"):
            op.drop_index("idx_ai_cost_events_tenant_created", table_name="ai_cost_events")
        op.drop_table("ai_cost_events")
    if _table_exists("tenant_token_budgets"):
        if _index_exists("idx_tenant_token_budgets_period"):
            op.drop_index("idx_tenant_token_budgets_period", table_name="tenant_token_budgets")
        op.drop_table("tenant_token_budgets")

