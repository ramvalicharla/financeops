"""Phase 5A Custom Report Builder

Revision ID: 0029_custom_report_builder
Revises: 0028_board_pack_generator
Create Date: 2026-03-19 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from financeops.db.append_only import append_only_function_sql, create_trigger_sql, drop_trigger_sql

revision: str = "0029_custom_report_builder"
down_revision: str | None = "0028_board_pack_generator"
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


def _enable_rls_with_policy(table_name: str) -> None:
    op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
    if not _policy_exists(table_name, "tenant_isolation"):
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table_name} "
            "USING (tenant_id = current_setting('app.current_tenant_id')::uuid)"
        )


def _ensure_append_only_trigger(table_name: str) -> None:
    op.execute(drop_trigger_sql(table_name))
    op.execute(create_trigger_sql(table_name))


def upgrade() -> None:
    if not _table_exists("report_definitions"):
        op.create_table(
            "report_definitions",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                nullable=False,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column(
                "metric_keys",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'[]'::jsonb"),
            ),
            sa.Column(
                "filter_config",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column(
                "group_by",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'[]'::jsonb"),
            ),
            sa.Column(
                "sort_config",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column(
                "export_formats",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'[\"CSV\",\"EXCEL\",\"PDF\"]'::jsonb"),
            ),
            sa.Column(
                "config",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
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
            sa.Column(
                "is_active",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
            ),
        )

    if not _table_exists("report_runs"):
        op.create_table(
            "report_runs",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                nullable=False,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("definition_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column(
                "status",
                sa.String(length=50),
                nullable=False,
                server_default=sa.text("'PENDING'"),
            ),
            sa.Column("triggered_by", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("row_count", sa.Integer(), nullable=True),
            sa.Column(
                "run_metadata",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.CheckConstraint(
                "status IN ('PENDING','RUNNING','COMPLETE','FAILED')",
                name="ck_report_runs_status",
            ),
            sa.ForeignKeyConstraint(
                ["definition_id"],
                ["report_definitions.id"],
                ondelete="RESTRICT",
            ),
        )

    if not _table_exists("report_results"):
        op.create_table(
            "report_results",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                nullable=False,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("result_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column("result_hash", sa.String(length=64), nullable=False),
            sa.Column("export_path_csv", sa.Text(), nullable=True),
            sa.Column("export_path_excel", sa.Text(), nullable=True),
            sa.Column("export_path_pdf", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.ForeignKeyConstraint(["run_id"], ["report_runs.id"], ondelete="RESTRICT"),
        )

    if (
        _column_exists("report_runs", "tenant_id")
        and _column_exists("report_runs", "definition_id")
        and _column_exists("report_runs", "created_at")
        and not _index_exists("idx_report_runs_tenant_definition_created_desc")
    ):
        op.execute(
            "CREATE INDEX idx_report_runs_tenant_definition_created_desc "
            "ON report_runs (tenant_id, definition_id, created_at DESC)"
        )

    if (
        _column_exists("report_runs", "tenant_id")
        and _column_exists("report_runs", "status")
        and not _index_exists("idx_report_runs_tenant_status")
    ):
        op.create_index(
            "idx_report_runs_tenant_status",
            "report_runs",
            ["tenant_id", "status"],
        )

    if _column_exists("report_results", "run_id") and not _index_exists("ux_report_results_run_id"):
        op.create_index(
            "ux_report_results_run_id",
            "report_results",
            ["run_id"],
            unique=True,
        )

    for table_name in ("report_definitions", "report_runs", "report_results"):
        if _table_exists(table_name):
            _enable_rls_with_policy(table_name)

    op.execute(append_only_function_sql())
    for table_name in ("report_runs", "report_results"):
        if _table_exists(table_name):
            _ensure_append_only_trigger(table_name)


def downgrade() -> None:
    if _table_exists("report_results"):
        op.drop_table("report_results")

    if (
        _table_exists("report_runs")
        and _column_exists("report_runs", "definition_id")
        and _column_exists("report_runs", "run_metadata")
    ):
        op.drop_table("report_runs")

    if (
        _table_exists("report_definitions")
        and _column_exists("report_definitions", "name")
        and _column_exists("report_definitions", "metric_keys")
    ):
        op.drop_table("report_definitions")
