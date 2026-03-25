"""add director and entity_user roles to user_role enum

Revision ID: 0067_add_director_role
Revises: 0066_auditor_portal
Create Date: 2026-03-25
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0067_add_director_role"
down_revision = "0066_auditor_portal"
branch_labels = None
depends_on = None


def _enum_value_exists(enum_name: str, enum_value: str) -> bool:
    bind = op.get_bind()
    return (
        bind.execute(
            sa.text(
                """
                SELECT 1
                FROM pg_enum e
                JOIN pg_type t ON e.enumtypid = t.oid
                WHERE t.typname = :enum_name
                  AND e.enumlabel = :enum_value
                LIMIT 1
                """
            ),
            {"enum_name": enum_name, "enum_value": enum_value},
        ).scalar_one_or_none()
        is not None
    )


def _add_user_role(enum_value: str) -> None:
    if _enum_value_exists("user_role_enum", enum_value):
        return
    op.execute(sa.text(f"ALTER TYPE user_role_enum ADD VALUE '{enum_value}'"))


def upgrade() -> None:
    _add_user_role("director")
    _add_user_role("entity_user")


def downgrade() -> None:
    # PostgreSQL enums do not support dropping individual values safely.
    pass

