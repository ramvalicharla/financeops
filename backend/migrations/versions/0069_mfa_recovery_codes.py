"""mfa recovery codes table

Revision ID: 0069_mfa_recovery_codes
Revises: 0068_entity_isolation
Create Date: 2026-03-25
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision = "0069_mfa_recovery_codes"
down_revision = "0068_entity_isolation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mfa_recovery_codes",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("iam_users.id"), nullable=False),
        sa.Column("code_hash", sa.VARCHAR(64), nullable=False),
        sa.Column("used_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mfa_recovery_codes_user", "mfa_recovery_codes", ["user_id"])
    op.create_index(
        "ix_mfa_recovery_codes_user_code",
        "mfa_recovery_codes",
        ["user_id", "code_hash"],
        unique=True,
    )

    op.execute("ALTER TABLE mfa_recovery_codes ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY mfa_recovery_codes_tenant_isolation
        ON mfa_recovery_codes
        USING (
            user_id IN (
                SELECT id FROM iam_users
                WHERE tenant_id = current_setting('app.tenant_id', true)::uuid
            )
        )
        """
    )


def downgrade() -> None:
    op.drop_table("mfa_recovery_codes")

