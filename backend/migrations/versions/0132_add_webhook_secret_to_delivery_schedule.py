"""add webhook_secret to delivery_schedules

Revision ID: 0132_webhook_secret_sched
Revises: 0131_reset_attempt_count_pwd
Create Date: 2026-04-15 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0132_webhook_secret_sched"
down_revision: str | None = "0131_reset_attempt_count_pwd"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


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


def upgrade() -> None:
    if not _column_exists("delivery_schedules", "webhook_secret"):
        op.add_column(
            "delivery_schedules",
            sa.Column("webhook_secret", sa.Text(), nullable=True),
        )


def downgrade() -> None:
    if _column_exists("delivery_schedules", "webhook_secret"):
        op.drop_column("delivery_schedules", "webhook_secret")
