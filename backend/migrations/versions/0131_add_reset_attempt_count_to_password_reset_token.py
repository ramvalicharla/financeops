"""add reset_attempt_count to password_reset_tokens

Revision ID: 0131_reset_attempt_count_pwd
Revises: 0130_iam_user_pwd_changed_at
Create Date: 2026-04-15 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0131_reset_attempt_count_pwd"
down_revision: str | None = "0130_iam_user_pwd_changed_at"
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
    if not _column_exists("password_reset_tokens", "reset_attempt_count"):
        op.add_column(
            "password_reset_tokens",
            sa.Column(
                "reset_attempt_count",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            ),
        )
        op.alter_column(
            "password_reset_tokens",
            "reset_attempt_count",
            server_default=None,
        )


def downgrade() -> None:
    if _column_exists("password_reset_tokens", "reset_attempt_count"):
        op.drop_column("password_reset_tokens", "reset_attempt_count")
