"""Search index table.

Revision ID: 0058_search_index
Revises: 0057_learning_engine
Create Date: 2026-03-24 23:55:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0058_search_index"
down_revision: str | None = "0057_learning_engine"
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


def upgrade() -> None:
    if not _table_exists("search_index_entries"):
        op.create_table(
            "search_index_entries",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                nullable=False,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("entity_type", sa.String(length=50), nullable=False),
            sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("title", sa.String(length=500), nullable=False),
            sa.Column("subtitle", sa.String(length=500), nullable=True),
            sa.Column("body", sa.Text(), nullable=True),
            sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
            sa.Column("url", sa.Text(), nullable=False),
            sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.UniqueConstraint("tenant_id", "entity_type", "entity_id", name="uq_search_index_entries_entity"),
        )

    if not _index_exists("idx_search_fts"):
        op.execute(
            "CREATE INDEX idx_search_fts ON search_index_entries "
            "USING gin(to_tsvector('english', title || ' ' || coalesce(subtitle, '') || ' ' || coalesce(body, '')))"
        )
    if not _index_exists("idx_search_index_entries_tenant_type_active"):
        op.execute(
            "CREATE INDEX idx_search_index_entries_tenant_type_active "
            "ON search_index_entries (tenant_id, entity_type, is_active)"
        )

    if _table_exists("search_index_entries"):
        op.execute("ALTER TABLE search_index_entries ENABLE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE search_index_entries FORCE ROW LEVEL SECURITY")
        if not _policy_exists("search_index_entries", "tenant_isolation"):
            op.execute(
                "CREATE POLICY tenant_isolation ON search_index_entries "
                f"USING (tenant_id = {_tenant_expr()})"
            )


def downgrade() -> None:
    if _index_exists("idx_search_index_entries_tenant_type_active") and _table_exists("search_index_entries"):
        op.drop_index("idx_search_index_entries_tenant_type_active", table_name="search_index_entries")
    if _index_exists("idx_search_fts") and _table_exists("search_index_entries"):
        op.drop_index("idx_search_fts", table_name="search_index_entries")
    if _table_exists("search_index_entries"):
        op.drop_table("search_index_entries")

