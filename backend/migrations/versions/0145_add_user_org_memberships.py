"""add user_org_memberships table with backfill

Revision ID: 0145_add_user_org_memberships
Revises: 0144_trial_plan_seed
Create Date: 2026-04-26

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0145_add_user_org_memberships"
down_revision = "0144_trial_plan_seed"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_org_memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "role",
            postgresql.ENUM(
                "super_admin", "platform_owner", "platform_admin", "platform_support",
                "org_admin", "finance_leader", "finance_team", "director",
                "entity_user", "auditor", "hr_manager", "employee", "read_only",
                name="user_role_enum",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("invited_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'active'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["iam_users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["iam_tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invited_by"], ["iam_users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("user_id", "tenant_id", name="uq_user_org"),
    )
    op.create_index("idx_uom_user_id", "user_org_memberships", ["user_id"])
    op.create_index("idx_uom_tenant_id", "user_org_memberships", ["tenant_id"])

    # Partial unique index: exactly one primary membership per user
    op.execute(
        "CREATE UNIQUE INDEX uq_user_one_primary "
        "ON user_org_memberships (user_id) "
        "WHERE is_primary = TRUE"
    )

    # Backfill: seed one membership row per existing user (their home org, primary)
    op.execute(
        """
        INSERT INTO user_org_memberships
            (id, user_id, tenant_id, role, is_primary, joined_at, status, created_at)
        SELECT
            gen_random_uuid(),
            u.id,
            u.tenant_id,
            u.role,
            TRUE,
            COALESCE(u.created_at, NOW()),
            'active',
            NOW()
        FROM iam_users u
        ON CONFLICT (user_id, tenant_id) DO NOTHING
        """
    )

    # Integrity check: every user must have exactly one primary membership row
    op.execute(
        """
        DO $$
        DECLARE mismatch int;
        BEGIN
          SELECT COUNT(*) INTO mismatch
          FROM iam_users u
          WHERE NOT EXISTS (
            SELECT 1 FROM user_org_memberships m
            WHERE m.user_id = u.id AND m.is_primary = TRUE
          );
          IF mismatch > 0 THEN
            RAISE EXCEPTION 'Backfill integrity check failed: % users missing primary membership', mismatch;
          END IF;
        END $$
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_user_one_primary")
    op.drop_index("idx_uom_tenant_id", table_name="user_org_memberships")
    op.drop_index("idx_uom_user_id", table_name="user_org_memberships")
    op.drop_table("user_org_memberships")
