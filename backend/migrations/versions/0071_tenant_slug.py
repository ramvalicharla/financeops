"""add slug to iam_tenants

Revision ID: 0071_tenant_slug
Revises: 0070_password_reset_tokens
Create Date: 2026-03-25
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0071_tenant_slug"
down_revision = "0070_password_reset_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("iam_tenants", sa.Column("slug", sa.VARCHAR(length=100), nullable=True))
    op.create_index("ix_iam_tenants_slug", "iam_tenants", ["slug"], unique=True)
    op.execute(
        """
        UPDATE iam_tenants
        SET slug = lower(trim(both '-' FROM regexp_replace(display_name, '[^a-zA-Z0-9]+', '-', 'g')))
        WHERE slug IS NULL
        """
    )
    op.alter_column("iam_tenants", "slug", nullable=False)


def downgrade() -> None:
    op.drop_index("ix_iam_tenants_slug", table_name="iam_tenants")
    op.drop_column("iam_tenants", "slug")

