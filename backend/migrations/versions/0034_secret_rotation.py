"""Phase 5G Secret Rotation

Revision ID: 0034_secret_rotation
Revises: 0033_template_onboarding
Create Date: 2026-03-21 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from financeops.db.append_only import append_only_function_sql, create_trigger_sql, drop_trigger_sql

revision: str = "0034_secret_rotation"
down_revision: str | None = "0033_template_onboarding"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PLATFORM_SENTINEL_UUID = "00000000-0000-0000-0000-000000000000"


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    value = bind.execute(
        sa.text("SELECT to_regclass(:table_name)"),
        {"table_name": f"public.{table_name}"},
    ).scalar_one_or_none()
    return value is not None


def _index_exists(index_name: str) -> bool:
    bind = op.get_bind()
    value = bind.execute(
        sa.text(
            """
            SELECT 1
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE c.relkind = 'i'
              AND n.nspname = 'public'
              AND c.relname = :index_name
            LIMIT 1
            """
        ),
        {"index_name": index_name},
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


def _enable_rls_with_policies(table_name: str) -> None:
    op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")

    if not _policy_exists(table_name, "tenant_isolation"):
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table_name} "
            "USING (tenant_id = COALESCE(NULLIF(current_setting('app.tenant_id', true), ''), NULLIF(current_setting('app.current_tenant_id', true), ''))::uuid)"
        )

    # Explicit platform-level sentinel visibility policy. Superadmin/platform
    # read paths can switch RLS context to PLATFORM_SENTINEL_UUID.
    if not _policy_exists(table_name, "platform_sentinel_visibility"):
        op.execute(
            f"CREATE POLICY platform_sentinel_visibility ON {table_name} "
            "USING ("
            f"tenant_id = '{PLATFORM_SENTINEL_UUID}'::uuid "
            "AND COALESCE(NULLIF(current_setting('app.tenant_id', true), ''), NULLIF(current_setting('app.current_tenant_id', true), ''))::uuid "
            f"= '{PLATFORM_SENTINEL_UUID}'::uuid"
            ")"
        )


def _ensure_append_only_trigger(table_name: str) -> None:
    op.execute(drop_trigger_sql(table_name))
    op.execute(create_trigger_sql(table_name))


def upgrade() -> None:
    if not _table_exists("secret_rotation_log"):
        op.create_table(
            "secret_rotation_log",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                nullable=False,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("secret_type", sa.String(length=50), nullable=False),
            sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("resource_type", sa.String(length=50), nullable=True),
            sa.Column("rotated_by", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column(
                "rotation_method",
                sa.String(length=20),
                nullable=False,
                server_default=sa.text("'manual'"),
            ),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("failure_reason", sa.Text(), nullable=True),
            sa.Column("previous_secret_hint", sa.String(length=8), nullable=True),
            sa.Column("new_secret_hint", sa.String(length=8), nullable=True),
            sa.Column(
                "initiated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.CheckConstraint(
                "secret_type IN ('smtp','webhook_signing','erp_api_key')",
                name="ck_secret_rotation_log_secret_type",
            ),
            sa.CheckConstraint(
                "rotation_method IN ('manual','scheduled','emergency')",
                name="ck_secret_rotation_log_rotation_method",
            ),
            sa.CheckConstraint(
                "status IN ('initiated','verified','completed','failed')",
                name="ck_secret_rotation_log_status",
            ),
            sa.CheckConstraint(
                "resource_type IS NULL OR resource_type IN ('delivery_schedule','erp_connector')",
                name="ck_secret_rotation_log_resource_type",
            ),
        )

    if _table_exists("secret_rotation_log") and not _index_exists("idx_secret_rotation_log_tenant_type_initiated_desc"):
        op.execute(
            "CREATE INDEX idx_secret_rotation_log_tenant_type_initiated_desc "
            "ON secret_rotation_log (tenant_id, secret_type, initiated_at DESC)"
        )

    if _table_exists("secret_rotation_log"):
        _enable_rls_with_policies("secret_rotation_log")

    op.execute(append_only_function_sql())
    if _table_exists("secret_rotation_log"):
        _ensure_append_only_trigger("secret_rotation_log")


def downgrade() -> None:
    if _table_exists("secret_rotation_log"):
        op.execute(drop_trigger_sql("secret_rotation_log"))
        op.drop_table("secret_rotation_log")
