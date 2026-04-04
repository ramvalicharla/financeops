"""allow_checklist_run_updates

Revision ID: 0113_checklist_run_mutable
Revises: 0112_board_pack_runs_compat
Create Date: 2026-04-03

Checklist run state transitions are mutable by design (open -> in_progress ->
completed/locked). Drop append-only trigger that blocked runtime updates.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from financeops.db.append_only import (
    append_only_function_sql,
    create_trigger_sql,
    drop_trigger_sql,
)


revision = "0113_checklist_run_mutable"
down_revision = "0112_board_pack_runs_compat"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    query = sa.text(
        """
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name = :table_name
        LIMIT 1
        """
    )
    return bind.execute(query, {"table_name": table_name}).scalar() is not None


def upgrade() -> None:
    if _table_exists("checklist_runs"):
        op.execute(drop_trigger_sql("checklist_runs"))


def downgrade() -> None:
    if _table_exists("checklist_runs"):
        op.execute(append_only_function_sql())
        op.execute(drop_trigger_sql("checklist_runs"))
        op.execute(create_trigger_sql("checklist_runs"))
