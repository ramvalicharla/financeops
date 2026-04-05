"""normalize iam user emails and enforce case-insensitive uniqueness

Revision ID: 0120_normalize_iam_user_emails
Revises: 0119_password_change_verified_flags
Create Date: 2026-04-05 15:30:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0120_normalize_iam_user_emails"
down_revision: Union[str, None] = "0119_pwd_change_flags"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    duplicate_rows = bind.execute(
        sa.text(
            """
            SELECT lower(trim(email)) AS normalized_email, count(*) AS row_count
            FROM iam_users
            GROUP BY lower(trim(email))
            HAVING count(*) > 1
            """
        )
    ).mappings().all()
    if duplicate_rows:
        duplicates = ", ".join(
            f"{row['normalized_email']} (count={row['row_count']})"
            for row in duplicate_rows
        )
        raise RuntimeError(
            "Cannot normalize iam_users.email because case-insensitive duplicates "
            f"exist: {duplicates}. Resolve the conflicting rows first and rerun "
            "the migration."
        )

    op.execute(
        sa.text(
            """
            UPDATE iam_users
            SET email = lower(trim(email))
            WHERE email IS DISTINCT FROM lower(trim(email))
            """
        )
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_iam_users_email_ci ON iam_users ((lower(email)))"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_iam_users_email_ci")
