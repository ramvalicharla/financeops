"""Phase 5 Board Pack Generator

Revision ID: 0028_board_pack_generator
Revises: 0027_payment_module
Create Date: 2026-03-18 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from financeops.db.append_only import append_only_function_sql, create_trigger_sql, drop_trigger_sql

revision: str = "0028_board_pack_generator"
down_revision: str | None = "0027_payment_module"
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
    if not _table_exists("board_pack_definitions"):
        op.create_table(
            "board_pack_definitions",
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
                "section_types",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'[]'::jsonb"),
            ),
            sa.Column(
                "entity_ids",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'[]'::jsonb"),
            ),
            sa.Column("period_type", sa.String(length=50), nullable=False),
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

    if not _table_exists("board_pack_runs"):
        op.create_table(
            "board_pack_runs",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                nullable=False,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("definition_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("period_start", sa.Date(), nullable=False),
            sa.Column("period_end", sa.Date(), nullable=False),
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
            sa.Column("chain_hash", sa.String(length=64), nullable=True),
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
                name="ck_board_pack_runs_generator_status",
            ),
            sa.ForeignKeyConstraint(
                ["definition_id"],
                ["board_pack_definitions.id"],
                ondelete="RESTRICT",
            ),
        )

    if not _table_exists("board_pack_sections"):
        op.create_table(
            "board_pack_sections",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                nullable=False,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("section_type", sa.String(length=50), nullable=False),
            sa.Column("section_order", sa.Integer(), nullable=False),
            sa.Column("data_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column("section_hash", sa.String(length=64), nullable=False),
            sa.Column(
                "rendered_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.ForeignKeyConstraint(["run_id"], ["board_pack_runs.id"], ondelete="RESTRICT"),
        )

    if not _table_exists("board_pack_artifacts"):
        op.create_table(
            "board_pack_artifacts",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                nullable=False,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("format", sa.String(length=20), nullable=False),
            sa.Column("storage_path", sa.Text(), nullable=False),
            sa.Column("file_size_bytes", sa.BigInteger(), nullable=True),
            sa.Column(
                "generated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column("checksum", sa.String(length=64), nullable=True),
            sa.CheckConstraint(
                "format IN ('PDF','EXCEL')",
                name="ck_board_pack_artifacts_format",
            ),
            sa.ForeignKeyConstraint(["run_id"], ["board_pack_runs.id"], ondelete="RESTRICT"),
        )

    if (
        _column_exists("board_pack_runs", "tenant_id")
        and _column_exists("board_pack_runs", "definition_id")
        and _column_exists("board_pack_runs", "created_at")
        and not _index_exists("idx_board_pack_runs_tenant_definition_created_desc")
    ):
        op.execute(
            "CREATE INDEX idx_board_pack_runs_tenant_definition_created_desc "
            "ON board_pack_runs (tenant_id, definition_id, created_at DESC)"
        )

    if (
        _column_exists("board_pack_runs", "tenant_id")
        and _column_exists("board_pack_runs", "status")
        and not _index_exists("idx_board_pack_runs_tenant_status")
    ):
        op.create_index(
            "idx_board_pack_runs_tenant_status",
            "board_pack_runs",
            ["tenant_id", "status"],
        )

    if (
        _column_exists("board_pack_sections", "run_id")
        and _column_exists("board_pack_sections", "section_order")
        and not _index_exists("idx_board_pack_sections_run_section_order")
    ):
        op.create_index(
            "idx_board_pack_sections_run_section_order",
            "board_pack_sections",
            ["run_id", "section_order"],
        )

    if (
        _column_exists("board_pack_artifacts", "run_id")
        and _column_exists("board_pack_artifacts", "format")
        and not _index_exists("idx_board_pack_artifacts_run_format")
    ):
        op.create_index(
            "idx_board_pack_artifacts_run_format",
            "board_pack_artifacts",
            ["run_id", "format"],
        )

    for table_name in (
        "board_pack_definitions",
        "board_pack_runs",
        "board_pack_sections",
        "board_pack_artifacts",
    ):
        if _table_exists(table_name):
            _enable_rls_with_policy(table_name)

    op.execute(append_only_function_sql())
    for table_name in ("board_pack_runs", "board_pack_sections", "board_pack_artifacts"):
        if _table_exists(table_name):
            _ensure_append_only_trigger(table_name)


def downgrade() -> None:
    if _table_exists("board_pack_artifacts"):
        op.drop_table("board_pack_artifacts")
    if _table_exists("board_pack_sections"):
        op.drop_table("board_pack_sections")

    # board_pack_runs / board_pack_definitions are pre-existing in this repository.
    # Only drop if this migration-style columns exist.
    if (
        _table_exists("board_pack_runs")
        and _column_exists("board_pack_runs", "definition_id")
        and _column_exists("board_pack_runs", "run_metadata")
    ):
        op.drop_table("board_pack_runs")

    if (
        _table_exists("board_pack_definitions")
        and _column_exists("board_pack_definitions", "name")
        and _column_exists("board_pack_definitions", "section_types")
    ):
        op.drop_table("board_pack_definitions")

