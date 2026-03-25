"""entity-level access isolation

Revision ID: 0068_entity_isolation
Revises: 0067_add_director_role
Create Date: 2026-03-25
"""

from __future__ import annotations

from alembic import op


# revision identifiers, used by Alembic.
revision = "0068_entity_isolation"
down_revision = "0067_add_director_role"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_user_entity_assignments_user_entity",
        "cp_user_entity_assignments",
        ["user_id", "entity_id", "is_active"],
    )
    op.create_index(
        "ix_user_entity_assignments_entity",
        "cp_user_entity_assignments",
        ["entity_id", "is_active"],
    )


def downgrade() -> None:
    op.drop_index("ix_user_entity_assignments_user_entity", table_name="cp_user_entity_assignments")
    op.drop_index("ix_user_entity_assignments_entity", table_name="cp_user_entity_assignments")

