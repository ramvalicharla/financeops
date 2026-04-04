"""Allow board-pack definition updates for API deactivation flow.

Revision ID: 0111_board_pack_defn_mutable
Revises: 0110_anomaly_threshold_mutable
Create Date: 2026-04-03 01:05:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

from financeops.db.append_only import (
    append_only_function_sql,
    create_trigger_sql,
    drop_trigger_sql,
)

revision: str = "0111_board_pack_defn_mutable"
down_revision: str | None = "0110_anomaly_threshold_mutable"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(drop_trigger_sql("board_pack_definitions"))


def downgrade() -> None:
    op.execute(append_only_function_sql())
    op.execute(create_trigger_sql("board_pack_definitions"))
