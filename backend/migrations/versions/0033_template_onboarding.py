"""Phase 5F Template Onboarding

Revision ID: 0033_template_onboarding
Revises: 0032_auto_trigger_pipeline
Create Date: 2026-03-21 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0033_template_onboarding"
down_revision: str | None = "0032_auto_trigger_pipeline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    value = bind.execute(
        sa.text("SELECT to_regclass(:table_name)"),
        {"table_name": f"public.{table_name}"},
    ).scalar_one_or_none()
    return value is not None


def _policy_exists(table_name: str, policy_name: str) -> bool:
    bind = op.get_bind()
    value = bind.execute(
        sa.text(
            """
            SELECT 1
            FROM pg_policies
            WHERE schemaname = 'public'
              AND tablename = :table_name
              AND policyname = :policy_name
            LIMIT 1
            """
        ),
        {"table_name": table_name, "policy_name": policy_name},
    ).scalar_one_or_none()
    return value is not None


def _enable_rls_with_policy(table_name: str) -> None:
    op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
    if not _policy_exists(table_name, "tenant_isolation"):
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table_name} "
            "USING (tenant_id = current_setting('app.current_tenant_id')::uuid)"
        )


def upgrade() -> None:
    if not _table_exists("onboarding_state"):
        op.create_table(
            "onboarding_state",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                nullable=False,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column(
                "tenant_id",
                postgresql.UUID(as_uuid=True),
                nullable=False,
            ),
            sa.Column(
                "current_step",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("1"),
            ),
            sa.Column("industry", sa.String(length=50), nullable=True),
            sa.Column(
                "template_applied",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column("template_applied_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("template_id", sa.String(length=50), nullable=True),
            sa.Column(
                "erp_connected",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column(
                "completed",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.CheckConstraint(
                "current_step >= 1 AND current_step <= 5",
                name="ck_onboarding_state_current_step",
            ),
            sa.CheckConstraint(
                "industry IS NULL OR industry IN ('saas','manufacturing','retail','professional_services','healthcare','general','it_services')",
                name="ck_onboarding_state_industry",
            ),
            sa.ForeignKeyConstraint(["tenant_id"], ["iam_tenants.id"], ondelete="CASCADE"),
            sa.UniqueConstraint("tenant_id", name="uq_onboarding_state_tenant_id"),
        )

    if _table_exists("onboarding_state"):
        _enable_rls_with_policy("onboarding_state")


def downgrade() -> None:
    if _table_exists("onboarding_state"):
        op.drop_table("onboarding_state")
