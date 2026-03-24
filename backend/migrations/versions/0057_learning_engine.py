"""Learning engine tables.

Revision ID: 0057_learning_engine
Revises: 0056_notifications
Create Date: 2026-03-24 23:35:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from financeops.db.append_only import append_only_function_sql, create_trigger_sql, drop_trigger_sql

revision: str = "0057_learning_engine"
down_revision: str | None = "0056_notifications"
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
    if not _table_exists("learning_signals"):
        op.create_table(
            "learning_signals",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                nullable=False,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("signal_type", sa.String(length=50), nullable=False),
            sa.Column("task_type", sa.String(length=50), nullable=False),
            sa.Column("original_ai_output", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column("human_correction", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column("correction_delta", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("model_used", sa.String(length=100), nullable=False),
            sa.Column("provider", sa.String(length=30), nullable=False),
            sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("session_id", sa.String(length=100), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.CheckConstraint(
                "signal_type IN ("
                "'classification_correction','commentary_edit','narrative_override',"
                "'anomaly_dismiss','anomaly_confirm','forecast_adjustment','variance_correction'"
                ")",
                name="ck_learning_signals_type",
            ),
        )

    if not _table_exists("learning_corrections"):
        op.create_table(
            "learning_corrections",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                nullable=False,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column(
                "signal_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("learning_signals.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("task_type", sa.String(length=50), nullable=False),
            sa.Column("input_context", sa.Text(), nullable=False),
            sa.Column("correct_output", sa.Text(), nullable=False),
            sa.Column("is_validated", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("validated_by", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("quality_score", sa.Numeric(3, 2), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        )

    if not _table_exists("ai_benchmark_results"):
        op.create_table(
            "ai_benchmark_results",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                nullable=False,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("benchmark_name", sa.String(length=100), nullable=False),
            sa.Column("benchmark_version", sa.String(length=20), nullable=False, server_default=sa.text("'1.0'")),
            sa.Column("model", sa.String(length=100), nullable=False),
            sa.Column("provider", sa.String(length=30), nullable=False),
            sa.Column("total_cases", sa.Integer(), nullable=False),
            sa.Column("passed_cases", sa.Integer(), nullable=False),
            sa.Column("accuracy_pct", sa.Numeric(5, 4), nullable=False),
            sa.Column("avg_latency_ms", sa.Numeric(8, 2), nullable=False),
            sa.Column("total_cost_usd", sa.Numeric(10, 6), nullable=False),
            sa.Column("run_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("run_by", sa.String(length=100), nullable=False),
            sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        )

    if not _index_exists("idx_learning_signals_tenant_type_created"):
        op.execute(
            "CREATE INDEX idx_learning_signals_tenant_type_created "
            "ON learning_signals (tenant_id, signal_type, created_at DESC)"
        )
    if not _index_exists("idx_learning_signals_tenant_task"):
        op.execute("CREATE INDEX idx_learning_signals_tenant_task ON learning_signals (tenant_id, task_type)")
    if not _index_exists("idx_learning_corrections_tenant_task_validated"):
        op.execute(
            "CREATE INDEX idx_learning_corrections_tenant_task_validated "
            "ON learning_corrections (tenant_id, task_type, is_validated)"
        )
    if not _index_exists("idx_ai_benchmark_results_name_run"):
        op.execute(
            "CREATE INDEX idx_ai_benchmark_results_name_run "
            "ON ai_benchmark_results (benchmark_name, run_at DESC)"
        )

    if _table_exists("learning_signals"):
        _enable_rls("learning_signals")
    if _table_exists("learning_corrections"):
        _enable_rls("learning_corrections")

    for table_name in ("learning_signals", "ai_benchmark_results"):
        if _table_exists(table_name):
            op.execute(append_only_function_sql())
            op.execute(drop_trigger_sql(table_name))
            op.execute(create_trigger_sql(table_name))


def downgrade() -> None:
    for table_name in ("ai_benchmark_results", "learning_signals"):
        if _table_exists(table_name):
            op.execute(drop_trigger_sql(table_name))

    if _index_exists("idx_ai_benchmark_results_name_run") and _table_exists("ai_benchmark_results"):
        op.drop_index("idx_ai_benchmark_results_name_run", table_name="ai_benchmark_results")
    if _index_exists("idx_learning_corrections_tenant_task_validated") and _table_exists("learning_corrections"):
        op.drop_index("idx_learning_corrections_tenant_task_validated", table_name="learning_corrections")
    if _index_exists("idx_learning_signals_tenant_task") and _table_exists("learning_signals"):
        op.drop_index("idx_learning_signals_tenant_task", table_name="learning_signals")
    if _index_exists("idx_learning_signals_tenant_type_created") and _table_exists("learning_signals"):
        op.drop_index("idx_learning_signals_tenant_type_created", table_name="learning_signals")

    if _table_exists("ai_benchmark_results"):
        op.drop_table("ai_benchmark_results")
    if _table_exists("learning_corrections"):
        op.drop_table("learning_corrections")
    if _table_exists("learning_signals"):
        op.drop_table("learning_signals")

