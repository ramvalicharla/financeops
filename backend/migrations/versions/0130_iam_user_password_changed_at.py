"""add password_changed_at to iam_users

Revision ID: 0130_iam_user_pwd_changed_at
Revises: 0129_phase4_4_closure_linkage
Create Date: 2026-04-15 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0130_iam_user_pwd_changed_at"
down_revision: str | None = "0129_phase4_4_closure_linkage"
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
    if not _column_exists("iam_users", "password_changed_at"):
        op.add_column(
            "iam_users",
            sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True),
        )


def downgrade() -> None:
    if _column_exists("iam_users", "password_changed_at"):
        op.drop_column("iam_users", "password_changed_at")
