"""Phase 5E Auto Trigger Pipeline

Revision ID: 0032_auto_trigger_pipeline
Revises: 0031_anomaly_ui_layer
Create Date: 2026-03-21 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from financeops.db.append_only import append_only_function_sql, create_trigger_sql, drop_trigger_sql

revision: str = "0032_auto_trigger_pipeline"
down_revision: str | None = "0031_anomaly_ui_layer"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    value = bind.execute(
        sa.text("SELECT to_regclass(:table_name)"),
        {"table_name": f"public.{table_name}"},
    ).scalar_one_or_none()
    return value is not None


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    value = bind.execute(
        sa.text(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = :table_name
              AND column_name = :column_name
            LIMIT 1
            """
        ),
        {"table_name": table_name, "column_name": column_name},
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


def _trigger_exists(table_name: str, trigger_name: str) -> bool:
    bind = op.get_bind()
    value = bind.execute(
        sa.text(
            """
            SELECT 1
            FROM information_schema.triggers
            WHERE event_object_schema = 'public'
              AND event_object_table = :table_name
              AND trigger_name = :trigger_name
            LIMIT 1
            """
        ),
        {"table_name": table_name, "trigger_name": trigger_name},
    ).scalar_one_or_none()
    return value is not None


def _function_exists(function_name: str) -> bool:
    bind = op.get_bind()
    value = bind.execute(
        sa.text(
            """
            SELECT 1
            FROM pg_proc p
            JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname = 'public'
              AND p.proname = :function_name
            LIMIT 1
            """
        ),
        {"function_name": function_name},
    ).scalar_one_or_none()
    return value is not None


def _enable_rls_with_policy(table_name: str) -> None:
    op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
    if not _policy_exists(table_name, "tenant_isolation"):
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table_name} "
            "USING (tenant_id = current_setting('app.current_tenant_id')::uuid)"
        )


def _create_pipeline_runs_update_guard() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION financeops_pipeline_runs_guard()
        RETURNS trigger AS $$
        BEGIN
          IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION 'append-only table "%": DELETE is not allowed', TG_TABLE_NAME
            USING ERRCODE = '55000';
          END IF;

          IF NEW.id <> OLD.id
             OR NEW.tenant_id <> OLD.tenant_id
             OR NEW.sync_run_id <> OLD.sync_run_id
             OR NEW.triggered_at <> OLD.triggered_at
             OR NEW.created_at <> OLD.created_at THEN
            RAISE EXCEPTION 'append-only table "%": UPDATE of immutable fields is not allowed', TG_TABLE_NAME
            USING ERRCODE = '55000';
          END IF;

          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )


def _ensure_pipeline_runs_guard_trigger() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_pipeline_runs_guard ON pipeline_runs")
    op.execute(
        """
        CREATE TRIGGER trg_pipeline_runs_guard
        BEFORE UPDATE OR DELETE ON pipeline_runs
        FOR EACH ROW EXECUTE FUNCTION financeops_pipeline_runs_guard();
        """
    )


def upgrade() -> None:
    if not _table_exists("pipeline_runs"):
        op.create_table(
            "pipeline_runs",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                nullable=False,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column(
                "sync_run_id",
                postgresql.UUID(as_uuid=True),
                nullable=False,
            ),
            sa.Column(
                "status",
                sa.String(length=20),
                nullable=False,
                server_default=sa.text("'running'"),
            ),
            sa.Column(
                "triggered_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.CheckConstraint(
                "status IN ('running','completed','failed','partial')",
                name="ck_pipeline_runs_status",
            ),
        )

    if not _table_exists("pipeline_step_logs"):
        op.create_table(
            "pipeline_step_logs",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                nullable=False,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column(
                "pipeline_run_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("pipeline_runs.id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("step_name", sa.String(length=50), nullable=False),
            sa.Column(
                "status",
                sa.String(length=20),
                nullable=False,
                server_default=sa.text("'running'"),
            ),
            sa.Column(
                "started_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("result_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.CheckConstraint(
                "step_name IN ('gl_reconciliation','payroll_reconciliation','mis_recomputation','anomaly_detection')",
                name="ck_pipeline_step_logs_step_name",
            ),
            sa.CheckConstraint(
                "status IN ('running','completed','failed','skipped')",
                name="ck_pipeline_step_logs_status",
            ),
        )

    if (
        _column_exists("pipeline_runs", "tenant_id")
        and _column_exists("pipeline_runs", "sync_run_id")
        and not _index_exists("uq_pipeline_runs_tenant_sync_active")
    ):
        op.execute(
            "CREATE UNIQUE INDEX uq_pipeline_runs_tenant_sync_active "
            "ON pipeline_runs (tenant_id, sync_run_id) "
            "WHERE status <> 'failed'"
        )

    if (
        _column_exists("pipeline_runs", "tenant_id")
        and _column_exists("pipeline_runs", "triggered_at")
        and not _index_exists("idx_pipeline_runs_tenant_triggered_desc")
    ):
        op.execute(
            "CREATE INDEX idx_pipeline_runs_tenant_triggered_desc "
            "ON pipeline_runs (tenant_id, triggered_at DESC)"
        )

    if (
        _column_exists("pipeline_step_logs", "pipeline_run_id")
        and _column_exists("pipeline_step_logs", "started_at")
        and not _index_exists("idx_pipeline_step_logs_run_started_desc")
    ):
        op.execute(
            "CREATE INDEX idx_pipeline_step_logs_run_started_desc "
            "ON pipeline_step_logs (pipeline_run_id, started_at DESC)"
        )

    if (
        _column_exists("pipeline_step_logs", "tenant_id")
        and _column_exists("pipeline_step_logs", "status")
        and not _index_exists("idx_pipeline_step_logs_tenant_status")
    ):
        op.create_index(
            "idx_pipeline_step_logs_tenant_status",
            "pipeline_step_logs",
            ["tenant_id", "status"],
        )

    for table_name in ("pipeline_runs", "pipeline_step_logs"):
        if _table_exists(table_name):
            _enable_rls_with_policy(table_name)

    if _table_exists("pipeline_runs"):
        _create_pipeline_runs_update_guard()
        _ensure_pipeline_runs_guard_trigger()

    op.execute(append_only_function_sql())
    if _table_exists("pipeline_step_logs"):
        op.execute(drop_trigger_sql("pipeline_step_logs"))
        op.execute(create_trigger_sql("pipeline_step_logs"))


def downgrade() -> None:
    if _table_exists("pipeline_step_logs"):
        op.execute(drop_trigger_sql("pipeline_step_logs"))
        op.drop_table("pipeline_step_logs")

    if _table_exists("pipeline_runs"):
        if _trigger_exists("pipeline_runs", "trg_pipeline_runs_guard"):
            op.execute("DROP TRIGGER IF EXISTS trg_pipeline_runs_guard ON pipeline_runs")
        op.drop_table("pipeline_runs")

    if _function_exists("financeops_pipeline_runs_guard"):
        op.execute("DROP FUNCTION IF EXISTS financeops_pipeline_runs_guard()")
