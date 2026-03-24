"""Auditor portal module.

Revision ID: 0066_auditor_portal
Revises: 0065_multi_gaap
Create Date: 2026-03-25 00:22:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from financeops.db.append_only import append_only_function_sql, create_trigger_sql, drop_trigger_sql

revision: str = "0066_auditor_portal"
down_revision: str | None = "0065_multi_gaap"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    value = bind.execute(sa.text("SELECT to_regclass(:table_name)"), {"table_name": f"public.{table_name}"}).scalar_one_or_none()
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
        op.execute(f"CREATE POLICY tenant_isolation ON {table_name} USING (tenant_id = {_tenant_expr()})")


def upgrade() -> None:
    if not _table_exists("auditor_portal_access"):
        op.create_table(
            "auditor_portal_access",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("auditor_email", sa.String(length=300), nullable=False),
            sa.Column("auditor_firm", sa.String(length=300), nullable=False),
            sa.Column("engagement_name", sa.String(length=300), nullable=False),
            sa.Column("access_level", sa.String(length=20), nullable=False, server_default=sa.text("'read_only'")),
            sa.Column("modules_accessible", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
            sa.Column("valid_from", sa.Date(), nullable=False),
            sa.Column("valid_until", sa.Date(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("access_token_hash", sa.String(length=64), nullable=False),
            sa.Column("last_accessed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("tenant_id", "auditor_email", "engagement_name", name="uq_auditor_portal_access_tenant_email_engagement"),
        )

    if not _table_exists("auditor_requests"):
        op.create_table(
            "auditor_requests",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
            sa.Column("access_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("request_number", sa.String(length=20), nullable=False),
            sa.Column("category", sa.String(length=50), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'open'")),
            sa.Column("due_date", sa.Date(), nullable=True),
            sa.Column("response_notes", sa.Text(), nullable=True),
            sa.Column("evidence_urls", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
            sa.Column("provided_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("provided_by", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.ForeignKeyConstraint(["access_id"], ["auditor_portal_access.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _index_exists("idx_auditor_requests_access_status"):
        op.create_index("idx_auditor_requests_access_status", "auditor_requests", ["access_id", "status"], unique=False)
    if not _index_exists("idx_auditor_requests_tenant_status_due"):
        op.create_index("idx_auditor_requests_tenant_status_due", "auditor_requests", ["tenant_id", "status", "due_date"], unique=False)

    if _table_exists("auditor_requests"):
        op.execute(sa.text(append_only_function_sql()))
        op.execute(sa.text(drop_trigger_sql("auditor_requests")))
        op.execute(sa.text(create_trigger_sql("auditor_requests")))

    if _table_exists("auditor_portal_access"):
        _enable_rls("auditor_portal_access")
    if _table_exists("auditor_requests"):
        _enable_rls("auditor_requests")


def downgrade() -> None:
    if _table_exists("auditor_requests"):
        op.execute(sa.text(drop_trigger_sql("auditor_requests")))
    if _table_exists("auditor_requests"):
        op.drop_table("auditor_requests")
    if _table_exists("auditor_portal_access"):
        op.drop_table("auditor_portal_access")
