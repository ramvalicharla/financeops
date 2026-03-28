"""ERP OAuth sessions and connection hardening.

Revision ID: 0084_erp_oauth_sessions_and_conn
Revises: 0083_entity_id_blockers
Create Date: 2026-03-28
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0084_erp_oauth_sessions_and_conn"
down_revision: str | None = "0083_entity_id_blockers"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    value = bind.execute(
        sa.text("SELECT to_regclass(:table_name)"),
        {"table_name": f"public.{table_name}"},
    ).scalar_one_or_none()
    return value is not None


def _column_exists(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def _index_exists(index_name: str) -> bool:
    bind = op.get_bind()
    return (
        bind.execute(sa.text("SELECT to_regclass(:name)"), {"name": index_name}).scalar_one_or_none()
        is not None
    )


def upgrade() -> None:
    if not _table_exists("erp_oauth_sessions"):
        op.create_table(
            "erp_oauth_sessions",
            sa.Column("id", UUID(as_uuid=True), nullable=False),
            sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
            sa.Column("entity_id", UUID(as_uuid=True), nullable=True),
            sa.Column("connection_id", UUID(as_uuid=True), nullable=False),
            sa.Column("provider", sa.String(length=32), nullable=False),
            sa.Column("state_token", sa.String(length=128), nullable=False),
            sa.Column("code_verifier_enc", sa.Text(), nullable=False),
            sa.Column("redirect_uri", sa.Text(), nullable=False),
            sa.Column("scopes", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=16), nullable=False, server_default="PENDING"),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("initiated_by_user_id", UUID(as_uuid=True), nullable=True),
            sa.Column("encrypted_tokens", sa.Text(), nullable=True),
            sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.ForeignKeyConstraint(["entity_id"], ["cp_entities.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["connection_id"], ["external_connections.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("state_token", name="uq_erp_oauth_sessions_state_token"),
        )

    if not _index_exists("idx_erp_oauth_sessions_connection_status"):
        op.create_index(
            "idx_erp_oauth_sessions_connection_status",
            "erp_oauth_sessions",
            ["connection_id", "status"],
        )
    if not _index_exists("idx_erp_oauth_sessions_tenant_created"):
        op.create_index(
            "idx_erp_oauth_sessions_tenant_created",
            "erp_oauth_sessions",
            ["tenant_id", "created_at"],
        )
    if not _index_exists("ix_erp_oauth_sessions_tenant_id"):
        op.create_index("ix_erp_oauth_sessions_tenant_id", "erp_oauth_sessions", ["tenant_id"])
    if not _index_exists("ix_erp_oauth_sessions_entity_id"):
        op.create_index("ix_erp_oauth_sessions_entity_id", "erp_oauth_sessions", ["entity_id"])
    if not _index_exists("ix_erp_oauth_sessions_connection_id"):
        op.create_index("ix_erp_oauth_sessions_connection_id", "erp_oauth_sessions", ["connection_id"])
    if not _index_exists("ix_erp_oauth_sessions_state_token"):
        op.create_index("ix_erp_oauth_sessions_state_token", "erp_oauth_sessions", ["state_token"])

    op.execute("ALTER TABLE erp_oauth_sessions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE erp_oauth_sessions FORCE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON erp_oauth_sessions")
    op.execute(
        "CREATE POLICY tenant_isolation ON erp_oauth_sessions "
        "USING (tenant_id = COALESCE(current_setting('app.tenant_id', true), current_setting('app.current_tenant_id', true))::uuid)"
    )

    for col_name, col_def in (
        ("encrypted_tokens", sa.Column("encrypted_tokens", sa.Text(), nullable=True)),
        ("token_expires_at", sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True)),
        ("token_refreshed_at", sa.Column("token_refreshed_at", sa.DateTime(timezone=True), nullable=True)),
        ("oauth_scopes", sa.Column("oauth_scopes", sa.Text(), nullable=True)),
    ):
        if not _column_exists("external_connections", col_name):
            op.add_column("external_connections", col_def)

    op.alter_column(
        "external_connections",
        "secret_ref",
        existing_type=sa.String(length=255),
        type_=sa.Text(),
        existing_nullable=True,
    )


def downgrade() -> None:
    for col_name in ("oauth_scopes", "token_refreshed_at", "token_expires_at", "encrypted_tokens"):
        if _column_exists("external_connections", col_name):
            op.drop_column("external_connections", col_name)

    op.alter_column(
        "external_connections",
        "secret_ref",
        existing_type=sa.Text(),
        type_=sa.String(length=255),
        existing_nullable=True,
        postgresql_using="left(secret_ref, 255)",
    )

    if _table_exists("erp_oauth_sessions"):
        op.execute("DROP POLICY IF EXISTS tenant_isolation ON erp_oauth_sessions")
        for idx_name in (
            "ix_erp_oauth_sessions_state_token",
            "ix_erp_oauth_sessions_connection_id",
            "ix_erp_oauth_sessions_entity_id",
            "ix_erp_oauth_sessions_tenant_id",
            "idx_erp_oauth_sessions_tenant_created",
            "idx_erp_oauth_sessions_connection_status",
        ):
            if _index_exists(idx_name):
                op.drop_index(idx_name, table_name="erp_oauth_sessions")
        op.drop_table("erp_oauth_sessions")
