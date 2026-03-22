"""GDPR Article 17 Right to Erasure implementation.

Revision ID: 0037_gdpr_erasure
Revises: 0036_encrypt_existing_secrets
Create Date: 2026-03-22 00:00:00.000000

erasure_log is append-only.
user_pii_keys is mutable - controlled exception for legal compliance.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from financeops.db.append_only import (
    append_only_function_sql,
    create_trigger_sql,
    drop_trigger_sql,
)

revision: str = "0037_gdpr_erasure"
down_revision: str | None = "0036_encrypt_existing_secrets"
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


def _enable_rls_with_policies(table_name: str) -> None:
    op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
    if not _policy_exists(table_name, "tenant_isolation"):
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table_name} "
            "USING (tenant_id = COALESCE(NULLIF(current_setting('app.tenant_id', true), ''), NULLIF(current_setting('app.current_tenant_id', true), ''))::uuid)"
        )


def upgrade() -> None:
    if not _table_exists("user_pii_keys"):
        op.create_table(
            "user_pii_keys",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                nullable=False,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
            sa.Column("encrypted_key", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column("erased_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["iam_users.id"], ondelete="CASCADE"),
        )
        op.create_index(
            "idx_user_pii_keys_tenant_user",
            "user_pii_keys",
            ["tenant_id", "user_id"],
        )

    if not _table_exists("erasure_log"):
        op.create_table(
            "erasure_log",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                nullable=False,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("user_id_hash", sa.String(length=64), nullable=False),
            sa.Column("requested_by", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("request_method", sa.String(length=20), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column(
                "pii_fields_erased",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'[]'::jsonb"),
            ),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.CheckConstraint(
                "request_method IN ('self','admin','regulatory')",
                name="ck_erasure_log_request_method",
            ),
            sa.CheckConstraint(
                "status IN ('initiated','completed','failed')",
                name="ck_erasure_log_status",
            ),
        )
        op.create_index(
            "idx_erasure_log_tenant_created",
            "erasure_log",
            ["tenant_id", "created_at"],
        )

    if _table_exists("user_pii_keys"):
        _enable_rls_with_policies("user_pii_keys")
    if _table_exists("erasure_log"):
        _enable_rls_with_policies("erasure_log")
        op.execute(append_only_function_sql())
        op.execute(drop_trigger_sql("erasure_log"))
        op.execute(create_trigger_sql("erasure_log"))


def downgrade() -> None:
    if _table_exists("erasure_log"):
        op.execute(drop_trigger_sql("erasure_log"))
        op.drop_index("idx_erasure_log_tenant_created", table_name="erasure_log")
        op.drop_table("erasure_log")
    if _table_exists("user_pii_keys"):
        op.drop_index("idx_user_pii_keys_tenant_user", table_name="user_pii_keys")
        op.drop_table("user_pii_keys")

