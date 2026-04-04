"""Normalize board_pack_runs schema for generator/narrative compatibility.

Revision ID: 0112_board_pack_runs_compat
Revises: 0111_board_pack_defn_mutable
Create Date: 2026-04-03 01:25:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0112_board_pack_runs_compat"
down_revision: str | None = "0111_board_pack_defn_mutable"
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


def _constraint_exists(table_name: str, constraint_name: str) -> bool:
    bind = op.get_bind()
    value = bind.execute(
        sa.text(
            """
            SELECT 1
            FROM information_schema.table_constraints
            WHERE table_schema = 'public'
              AND table_name = :table_name
              AND constraint_name = :constraint_name
            LIMIT 1
            """
        ),
        {"table_name": table_name, "constraint_name": constraint_name},
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


def _foreign_key_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    value = bind.execute(
        sa.text(
            """
            SELECT 1
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name
             AND tc.table_schema = kcu.table_schema
            WHERE tc.table_schema = 'public'
              AND tc.table_name = :table_name
              AND tc.constraint_type = 'FOREIGN KEY'
              AND kcu.column_name = :column_name
            LIMIT 1
            """
        ),
        {"table_name": table_name, "column_name": column_name},
    ).scalar_one_or_none()
    return value is not None


def upgrade() -> None:
    if _table_exists("board_pack_definitions"):
        if not _column_exists("board_pack_definitions", "name"):
            op.execute("ALTER TABLE board_pack_definitions ADD COLUMN name VARCHAR(255)")
        if not _column_exists("board_pack_definitions", "description"):
            op.execute("ALTER TABLE board_pack_definitions ADD COLUMN description TEXT")
        if not _column_exists("board_pack_definitions", "section_types"):
            op.execute(
                "ALTER TABLE board_pack_definitions "
                "ADD COLUMN section_types JSONB NOT NULL DEFAULT '[]'::jsonb"
            )
        if not _column_exists("board_pack_definitions", "entity_ids"):
            op.execute(
                "ALTER TABLE board_pack_definitions "
                "ADD COLUMN entity_ids JSONB NOT NULL DEFAULT '[]'::jsonb"
            )
        if not _column_exists("board_pack_definitions", "period_type"):
            op.execute("ALTER TABLE board_pack_definitions ADD COLUMN period_type VARCHAR(50)")
        if not _column_exists("board_pack_definitions", "config"):
            op.execute(
                "ALTER TABLE board_pack_definitions "
                "ADD COLUMN config JSONB NOT NULL DEFAULT '{}'::jsonb"
            )
        if not _column_exists("board_pack_definitions", "created_by"):
            op.execute("ALTER TABLE board_pack_definitions ADD COLUMN created_by UUID")
        if not _column_exists("board_pack_definitions", "updated_at"):
            op.execute(
                "ALTER TABLE board_pack_definitions "
                "ADD COLUMN updated_at TIMESTAMPTZ NOT NULL DEFAULT now()"
            )
        if not _column_exists("board_pack_definitions", "is_active"):
            op.execute(
                "ALTER TABLE board_pack_definitions "
                "ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT true"
            )

    if not _table_exists("board_pack_runs"):
        return

    if not _column_exists("board_pack_runs", "definition_id"):
        op.execute("ALTER TABLE board_pack_runs ADD COLUMN definition_id UUID")
    if not _column_exists("board_pack_runs", "period_start"):
        op.execute("ALTER TABLE board_pack_runs ADD COLUMN period_start DATE")
    if not _column_exists("board_pack_runs", "period_end"):
        op.execute("ALTER TABLE board_pack_runs ADD COLUMN period_end DATE")
    if not _column_exists("board_pack_runs", "triggered_by"):
        op.execute("ALTER TABLE board_pack_runs ADD COLUMN triggered_by UUID")
    if not _column_exists("board_pack_runs", "started_at"):
        op.execute("ALTER TABLE board_pack_runs ADD COLUMN started_at TIMESTAMPTZ")
    if not _column_exists("board_pack_runs", "completed_at"):
        op.execute("ALTER TABLE board_pack_runs ADD COLUMN completed_at TIMESTAMPTZ")
    if not _column_exists("board_pack_runs", "error_message"):
        op.execute("ALTER TABLE board_pack_runs ADD COLUMN error_message TEXT")
    if not _column_exists("board_pack_runs", "run_metadata"):
        op.execute(
            "ALTER TABLE board_pack_runs "
            "ADD COLUMN run_metadata JSONB NOT NULL DEFAULT '{}'::jsonb"
        )

    if _constraint_exists("board_pack_runs", "ck_board_pack_runs_status"):
        op.execute("ALTER TABLE board_pack_runs DROP CONSTRAINT ck_board_pack_runs_status")
    if _constraint_exists("board_pack_runs", "ck_board_pack_runs_generator_status"):
        op.execute("ALTER TABLE board_pack_runs DROP CONSTRAINT ck_board_pack_runs_generator_status")
    if _constraint_exists("board_pack_runs", "ck_board_pack_runs_status_compat"):
        op.execute("ALTER TABLE board_pack_runs DROP CONSTRAINT ck_board_pack_runs_status_compat")

    op.execute(
        """
        ALTER TABLE board_pack_runs
        ADD CONSTRAINT ck_board_pack_runs_status
        CHECK (upper(status) IN ('CREATED','RUNNING','COMPLETED','FAILED','PENDING','COMPLETE'))
        """
    )

    if _column_exists("board_pack_runs", "definition_id") and not _index_exists(
        "idx_board_pack_runs_tenant_definition_created_desc"
    ):
        op.execute(
            "CREATE INDEX idx_board_pack_runs_tenant_definition_created_desc "
            "ON board_pack_runs (tenant_id, definition_id, created_at DESC)"
        )
    if not _index_exists("idx_board_pack_runs_tenant_status"):
        op.execute("CREATE INDEX idx_board_pack_runs_tenant_status ON board_pack_runs (tenant_id, status)")

    if (
        _table_exists("board_pack_definitions")
        and _column_exists("board_pack_runs", "definition_id")
        and not _foreign_key_exists("board_pack_runs", "definition_id")
    ):
        op.execute(
            """
            ALTER TABLE board_pack_runs
            ADD CONSTRAINT fk_board_pack_runs_definition_id
            FOREIGN KEY (definition_id)
            REFERENCES board_pack_definitions(id)
            ON DELETE RESTRICT
            NOT VALID
            """
        )


def downgrade() -> None:
    # Deliberately non-destructive: removing compatibility columns/constraint can drop data.
    pass
