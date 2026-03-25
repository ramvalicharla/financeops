"""user invite token fields

Revision ID: 0073_user_invite_tokens
Revises: 0072_terms_acceptance
Create Date: 2026-03-25
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0073_user_invite_tokens"
down_revision = "0072_terms_acceptance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("iam_users", sa.Column("invite_token_hash", sa.VARCHAR(64), nullable=True))
    op.add_column("iam_users", sa.Column("invite_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("iam_users", sa.Column("invite_accepted_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(
        "ix_iam_users_invite_token",
        "iam_users",
        ["invite_token_hash"],
        unique=True,
        postgresql_where=sa.text("invite_token_hash IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_iam_users_invite_token", table_name="iam_users")
    op.drop_column("iam_users", "invite_token_hash")
    op.drop_column("iam_users", "invite_expires_at")
    op.drop_column("iam_users", "invite_accepted_at")
