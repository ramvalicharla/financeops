"""Platform bootstrap columns and sentinel tenant.

Revision ID: 0048_platform_bootstrap
Revises: 0047_backup_dr
Create Date: 2026-03-23 23:59:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0048_platform_bootstrap"
down_revision: str | None = "0047_backup_dr"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    value = bind.execute(
        sa.text(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = :table_name
              AND column_name = :column_name
            LIMIT 1
            """
        ),
        {"table_name": table_name, "column_name": column_name},
    ).scalar_one_or_none()
    return value is not None


def _enum_value_exists(enum_name: str, enum_value: str) -> bool:
    bind = op.get_bind()
    value = bind.execute(
        sa.text(
            """
            SELECT 1
            FROM pg_type t
            JOIN pg_enum e ON t.oid = e.enumtypid
            WHERE t.typname = :enum_name
              AND e.enumlabel = :enum_value
            LIMIT 1
            """
        ),
        {"enum_name": enum_name, "enum_value": enum_value},
    ).scalar_one_or_none()
    return value is not None


def _tenant_exists(tenant_id: str) -> bool:
    bind = op.get_bind()
    value = bind.execute(
        sa.text("SELECT 1 FROM iam_tenants WHERE id = CAST(:tenant_id AS uuid) LIMIT 1"),
        {"tenant_id": tenant_id},
    ).scalar_one_or_none()
    return value is not None


def _add_user_role(enum_value: str) -> None:
    if _enum_value_exists("user_role_enum", enum_value):
        return
    op.execute(sa.text(f"ALTER TYPE user_role_enum ADD VALUE '{enum_value}'"))


def upgrade() -> None:
    _add_user_role("platform_owner")
    _add_user_role("platform_admin")
    _add_user_role("platform_support")

    if not _column_exists("iam_tenants", "is_platform_tenant"):
        op.add_column(
            "iam_tenants",
            sa.Column(
                "is_platform_tenant",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )
    if not _column_exists("iam_users", "force_mfa_setup"):
        op.add_column(
            "iam_users",
            sa.Column(
                "force_mfa_setup",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )

    platform_tenant_id = "00000000-0000-0000-0000-000000000000"
    if not _tenant_exists(platform_tenant_id):
        bind = op.get_bind()
        bind.execute(
            sa.text(
                """
                INSERT INTO iam_tenants (
                    id,
                    tenant_id,
                    chain_hash,
                    previous_hash,
                    created_at,
                    display_name,
                    tenant_type,
                    parent_tenant_id,
                    country,
                    timezone,
                    status,
                    is_platform_tenant
                ) VALUES (
                    CAST(:tenant_id AS uuid),
                    CAST(:tenant_id AS uuid),
                    repeat('0', 64),
                    repeat('0', 64),
                    now(),
                    'FinanceOps Platform',
                    'direct',
                    NULL,
                    'US',
                    'UTC',
                    'active',
                    true
                )
                """
            ),
            {"tenant_id": platform_tenant_id},
        )


def downgrade() -> None:
    platform_tenant_id = "00000000-0000-0000-0000-000000000000"
    if _tenant_exists(platform_tenant_id):
        bind = op.get_bind()
        bind.execute(
            sa.text("DELETE FROM iam_tenants WHERE id = CAST(:tenant_id AS uuid)"),
            {"tenant_id": platform_tenant_id},
        )

    if _column_exists("iam_users", "force_mfa_setup"):
        op.drop_column("iam_users", "force_mfa_setup")
    if _column_exists("iam_tenants", "is_platform_tenant"):
        op.drop_column("iam_tenants", "is_platform_tenant")
