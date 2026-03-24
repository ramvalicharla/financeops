"""Digital signoff module.

Revision ID: 0063_director_signoff
Revises: 0062_transfer_pricing
Create Date: 2026-03-25 00:12:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from financeops.db.append_only import append_only_function_sql, create_trigger_sql, drop_trigger_sql

revision: str = "0063_director_signoff"
down_revision: str | None = "0062_transfer_pricing"
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
    if not _table_exists("director_signoffs"):
        op.create_table(
            "director_signoffs",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("document_type", sa.String(length=50), nullable=False),
            sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("document_reference", sa.String(length=300), nullable=False),
            sa.Column("period", sa.String(length=7), nullable=False),
            sa.Column("signatory_user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("signatory_name", sa.String(length=300), nullable=False),
            sa.Column("signatory_role", sa.String(length=100), nullable=False),
            sa.Column("mfa_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("mfa_verified_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("ip_address", sa.String(length=45), nullable=True),
            sa.Column("user_agent", sa.String(length=500), nullable=True),
            sa.Column("declaration_text", sa.Text(), nullable=False),
            sa.Column("content_hash", sa.String(length=64), nullable=False),
            sa.Column("signature_hash", sa.String(length=64), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'pending'")),
            sa.Column("signed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("revocation_reason", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _index_exists("idx_director_signoffs_tenant_doc_period"):
        op.create_index("idx_director_signoffs_tenant_doc_period", "director_signoffs", ["tenant_id", "document_type", "period"], unique=False)
    if not _index_exists("idx_director_signoffs_tenant_signatory"):
        op.create_index("idx_director_signoffs_tenant_signatory", "director_signoffs", ["tenant_id", "signatory_user_id"], unique=False)

    if _table_exists("director_signoffs"):
        op.execute(sa.text(append_only_function_sql()))
        op.execute(sa.text(drop_trigger_sql("director_signoffs")))
        op.execute(sa.text(create_trigger_sql("director_signoffs")))
        _enable_rls("director_signoffs")


def downgrade() -> None:
    if _table_exists("director_signoffs"):
        op.execute(sa.text(drop_trigger_sql("director_signoffs")))
        op.drop_table("director_signoffs")
