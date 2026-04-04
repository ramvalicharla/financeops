"""add password-change and verification flags to iam_users

Revision ID: 0119_pwd_change_flags
Revises: 0118_ppa_alloc_mutable
Create Date: 2026-04-04 20:40:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0119_pwd_change_flags"
down_revision: str | None = "0118_ppa_alloc_mutable"
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
    if not _column_exists("iam_users", "is_verified"):
        op.add_column(
            "iam_users",
            sa.Column(
                "is_verified",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
            ),
        )
    if not _column_exists("iam_users", "force_password_change"):
        op.add_column(
            "iam_users",
            sa.Column(
                "force_password_change",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )


def downgrade() -> None:
    if _column_exists("iam_users", "force_password_change"):
        op.drop_column("iam_users", "force_password_change")
    if _column_exists("iam_users", "is_verified"):
        op.drop_column("iam_users", "is_verified")
