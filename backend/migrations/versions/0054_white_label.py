"""White-label branding configuration and audit tables.

Revision ID: 0054_white_label
Revises: 0053_marketplace
Create Date: 2026-03-24 21:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from financeops.db.append_only import append_only_function_sql, create_trigger_sql, drop_trigger_sql

revision: str = "0054_white_label"
down_revision: str | None = "0053_marketplace"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


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


def _tenant_expr() -> str:
    return (
        "COALESCE(NULLIF(current_setting('app.tenant_id', true), ''), "
        "NULLIF(current_setting('app.current_tenant_id', true), ''))::uuid"
    )


def _enable_rls(table_name: str) -> None:
    op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
    if not _policy_exists(table_name, "tenant_isolation"):
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table_name} "
            f"USING (tenant_id = {_tenant_expr()})"
        )


def upgrade() -> None:
    if not _table_exists("white_label_configs"):
        op.create_table(
            "white_label_configs",
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
                sa.ForeignKey("iam_tenants.id", ondelete="CASCADE"),
                nullable=False,
                unique=True,
            ),
            sa.Column(
                "is_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column("custom_domain", sa.String(length=300), nullable=True),
            sa.Column(
                "domain_verified",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column("domain_verification_token", sa.String(length=100), nullable=True),
            sa.Column("brand_name", sa.String(length=200), nullable=True),
            sa.Column("logo_url", sa.Text(), nullable=True),
            sa.Column("favicon_url", sa.Text(), nullable=True),
            sa.Column("primary_colour", sa.String(length=7), nullable=True),
            sa.Column("secondary_colour", sa.String(length=7), nullable=True),
            sa.Column("font_family", sa.String(length=100), nullable=True),
            sa.Column(
                "hide_powered_by",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column("custom_css", sa.Text(), nullable=True),
            sa.Column("support_email", sa.String(length=300), nullable=True),
            sa.Column("support_url", sa.Text(), nullable=True),
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
            sa.UniqueConstraint("tenant_id", name="uq_white_label_configs_tenant_id"),
        )

    if not _table_exists("white_label_audit_log"):
        op.create_table(
            "white_label_audit_log",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                nullable=False,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column(
                "changed_by",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("iam_users.id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column("field_changed", sa.String(length=100), nullable=False),
            sa.Column("old_value", sa.Text(), nullable=True),
            sa.Column("new_value", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
        )

    if not _index_exists("idx_white_label_configs_custom_domain_unique"):
        op.execute(
            "CREATE UNIQUE INDEX idx_white_label_configs_custom_domain_unique "
            "ON white_label_configs (custom_domain) WHERE custom_domain IS NOT NULL"
        )
    if not _index_exists("idx_white_label_audit_log_tenant_created"):
        op.execute(
            "CREATE INDEX idx_white_label_audit_log_tenant_created "
            "ON white_label_audit_log (tenant_id, created_at DESC)"
        )

    if _table_exists("white_label_configs"):
        _enable_rls("white_label_configs")
    if _table_exists("white_label_audit_log"):
        _enable_rls("white_label_audit_log")

    if _table_exists("white_label_audit_log"):
        op.execute(append_only_function_sql())
        op.execute(drop_trigger_sql("white_label_audit_log"))
        op.execute(create_trigger_sql("white_label_audit_log"))


def downgrade() -> None:
    if _table_exists("white_label_audit_log"):
        op.execute(drop_trigger_sql("white_label_audit_log"))

    if _index_exists("idx_white_label_audit_log_tenant_created") and _table_exists("white_label_audit_log"):
        op.drop_index("idx_white_label_audit_log_tenant_created", table_name="white_label_audit_log")
    if _index_exists("idx_white_label_configs_custom_domain_unique") and _table_exists("white_label_configs"):
        op.drop_index("idx_white_label_configs_custom_domain_unique", table_name="white_label_configs")

    if _table_exists("white_label_audit_log"):
        op.drop_table("white_label_audit_log")
    if _table_exists("white_label_configs"):
        op.drop_table("white_label_configs")

