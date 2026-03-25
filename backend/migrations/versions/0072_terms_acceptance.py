"""add terms acceptance to iam_users

Revision ID: 0072_terms_acceptance
Revises: 0071_tenant_slug
Create Date: 2026-03-25
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0072_terms_acceptance"
down_revision = "0071_tenant_slug"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "iam_users",
        sa.Column("terms_accepted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "iam_users",
        sa.Column("terms_version_accepted", sa.String(length=20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("iam_users", "terms_version_accepted")
    op.drop_column("iam_users", "terms_accepted_at")

