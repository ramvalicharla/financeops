"""add display scale preferences to tenant and user

Revision ID: 0074_display_scale_preferences
Revises: 0073_user_invite_tokens
Create Date: 2026-03-26
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0074_display_scale_preferences"
down_revision = "0073_user_invite_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "iam_tenants",
        sa.Column(
            "default_display_scale",
            sa.VARCHAR(20),
            nullable=False,
            server_default="LAKHS",
        ),
    )
    op.add_column(
        "iam_tenants",
        sa.Column(
            "default_currency",
            sa.VARCHAR(3),
            nullable=False,
            server_default="INR",
        ),
    )
    op.add_column(
        "iam_tenants",
        sa.Column(
            "number_format_locale",
            sa.VARCHAR(20),
            nullable=False,
            server_default="en-IN",
        ),
    )
    op.add_column(
        "iam_users",
        sa.Column(
            "display_scale_override",
            sa.VARCHAR(20),
            nullable=True,
        ),
    )
    op.create_check_constraint(
        "ck_tenant_display_scale_valid",
        "iam_tenants",
        "default_display_scale IN ('INR','LAKHS','CRORES','THOUSANDS','MILLIONS','BILLIONS')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_tenant_display_scale_valid", "iam_tenants")
    op.drop_column("iam_tenants", "default_display_scale")
    op.drop_column("iam_tenants", "default_currency")
    op.drop_column("iam_tenants", "number_format_locale")
    op.drop_column("iam_users", "display_scale_override")

