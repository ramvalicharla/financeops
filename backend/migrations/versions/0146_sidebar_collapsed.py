"""add sidebar_collapsed preference to iam_users

Revision ID: 0146_sidebar_collapsed
Revises: 0145_add_user_org_memberships
Create Date: 2026-04-27

NULL = no preference set; frontend falls back to localStorage default.
No backfill — existing users keep their localStorage value until next toggle.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0146_sidebar_collapsed"
down_revision = "0145_add_user_org_memberships"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "iam_users",
        sa.Column(
            "sidebar_collapsed",
            sa.Boolean(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("iam_users", "sidebar_collapsed")
