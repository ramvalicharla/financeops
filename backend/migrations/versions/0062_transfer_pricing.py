"""Transfer pricing module.

Revision ID: 0062_transfer_pricing
Revises: 0061_debt_covenants
Create Date: 2026-03-25 00:08:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from financeops.db.append_only import append_only_function_sql, create_trigger_sql, drop_trigger_sql

revision: str = "0062_transfer_pricing"
down_revision: str | None = "0061_debt_covenants"
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
    if not _table_exists("tp_configs"):
        op.create_table(
            "tp_configs",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("consolidated_revenue_threshold", sa.Numeric(20, 2), nullable=False, server_default=sa.text("50000000")),
            sa.Column("international_transactions_exist", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("specified_domestic_transactions_exist", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("applicable_methods", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("tenant_id"),
        )

    if not _table_exists("ic_transactions"):
        op.create_table(
            "ic_transactions",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("fiscal_year", sa.Integer(), nullable=False),
            sa.Column("transaction_type", sa.String(length=50), nullable=False),
            sa.Column("related_party_name", sa.String(length=300), nullable=False),
            sa.Column("related_party_country", sa.String(length=3), nullable=False),
            sa.Column("transaction_amount", sa.Numeric(20, 2), nullable=False),
            sa.Column("currency", sa.String(length=3), nullable=False),
            sa.Column("transaction_amount_inr", sa.Numeric(20, 2), nullable=False),
            sa.Column("pricing_method", sa.String(length=10), nullable=False),
            sa.Column("arm_length_price", sa.Numeric(20, 2), nullable=True),
            sa.Column("actual_price", sa.Numeric(20, 2), nullable=True),
            sa.Column("adjustment_required", sa.Numeric(20, 2), nullable=False, server_default=sa.text("0")),
            sa.Column("is_international", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _table_exists("transfer_pricing_docs"):
        op.create_table(
            "transfer_pricing_docs",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("fiscal_year", sa.Integer(), nullable=False),
            sa.Column("document_type", sa.String(length=20), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
            sa.Column("content", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("ai_narrative", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'draft'")),
            sa.Column("filed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _index_exists("idx_ic_transactions_tenant_fiscal_year"):
        op.create_index("idx_ic_transactions_tenant_fiscal_year", "ic_transactions", ["tenant_id", "fiscal_year"], unique=False)
    if not _index_exists("idx_transfer_pricing_docs_tenant_year_type"):
        op.create_index("idx_transfer_pricing_docs_tenant_year_type", "transfer_pricing_docs", ["tenant_id", "fiscal_year", "document_type"], unique=False)

    if _table_exists("ic_transactions"):
        op.execute(sa.text(append_only_function_sql()))
        op.execute(sa.text(drop_trigger_sql("ic_transactions")))
        op.execute(sa.text(create_trigger_sql("ic_transactions")))
    if _table_exists("transfer_pricing_docs"):
        op.execute(sa.text(append_only_function_sql()))
        op.execute(sa.text(drop_trigger_sql("transfer_pricing_docs")))
        op.execute(sa.text(create_trigger_sql("transfer_pricing_docs")))

    if _table_exists("tp_configs"):
        _enable_rls("tp_configs")
    if _table_exists("ic_transactions"):
        _enable_rls("ic_transactions")
    if _table_exists("transfer_pricing_docs"):
        _enable_rls("transfer_pricing_docs")


def downgrade() -> None:
    if _table_exists("ic_transactions"):
        op.execute(sa.text(drop_trigger_sql("ic_transactions")))
    if _table_exists("transfer_pricing_docs"):
        op.execute(sa.text(drop_trigger_sql("transfer_pricing_docs")))

    if _table_exists("transfer_pricing_docs"):
        op.drop_table("transfer_pricing_docs")
    if _table_exists("ic_transactions"):
        op.drop_table("ic_transactions")
    if _table_exists("tp_configs"):
        op.drop_table("tp_configs")
