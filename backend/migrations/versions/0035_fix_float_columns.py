"""Fix float columns in ai_prompt_versions

Revision ID: 0035_fix_float_columns
Revises: 0034_secret_rotation
Create Date: 2026-03-22 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0035_fix_float_columns"
down_revision: str | None = "0034_secret_rotation"
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


def _column_data_type(table_name: str, column_name: str) -> str | None:
    bind = op.get_bind()
    return bind.execute(
        sa.text(
            """
            SELECT data_type
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = :table_name
              AND column_name = :column_name
            LIMIT 1
            """
        ),
        {"table_name": table_name, "column_name": column_name},
    ).scalar_one_or_none()


def upgrade() -> None:
    if _column_exists("ai_prompt_versions", "acceptance_rate"):
        acceptance_rate_type = _column_data_type("ai_prompt_versions", "acceptance_rate")
        if acceptance_rate_type in {"double precision", "real"}:
            op.execute(
                """
                ALTER TABLE ai_prompt_versions
                ALTER COLUMN acceptance_rate TYPE numeric(5,4)
                USING acceptance_rate::numeric(5,4)
                """
            )

    if _column_exists("ai_prompt_versions", "is_active"):
        is_active_type = _column_data_type("ai_prompt_versions", "is_active")
        if is_active_type in {"integer", "smallint", "bigint"}:
            op.execute(
                """
                ALTER TABLE ai_prompt_versions
                ALTER COLUMN is_active TYPE boolean
                USING (is_active != 0)
                """
            )


def downgrade() -> None:
    if _column_exists("ai_prompt_versions", "acceptance_rate"):
        acceptance_rate_type = _column_data_type("ai_prompt_versions", "acceptance_rate")
        if acceptance_rate_type == "numeric":
            op.execute(
                """
                ALTER TABLE ai_prompt_versions
                ALTER COLUMN acceptance_rate TYPE float
                USING acceptance_rate::float
                """
            )

    if _column_exists("ai_prompt_versions", "is_active"):
        is_active_type = _column_data_type("ai_prompt_versions", "is_active")
        if is_active_type == "boolean":
            op.execute(
                """
                ALTER TABLE ai_prompt_versions
                ALTER COLUMN is_active TYPE integer
                USING (is_active::int)
                """
            )
