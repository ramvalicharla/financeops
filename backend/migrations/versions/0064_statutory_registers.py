"""Statutory registers module.

Revision ID: 0064_statutory_registers
Revises: 0063_director_signoff
Create Date: 2026-03-25 00:16:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from financeops.db.append_only import append_only_function_sql, create_trigger_sql, drop_trigger_sql

revision: str = "0064_statutory_registers"
down_revision: str | None = "0063_director_signoff"
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


def _seed_forms() -> None:
    op.execute(
        sa.text(
            """
            INSERT INTO statutory_filings (tenant_id, form_number, form_description, due_date, status)
            SELECT t.id, seeded.form_number, seeded.form_description, seeded.due_date, 'pending'
            FROM iam_tenants t
            CROSS JOIN (
                VALUES
                    ('MGT-7', 'Annual Return', make_date(EXTRACT(YEAR FROM CURRENT_DATE)::int, 11, 30)),
                    ('AOC-4', 'Financial Statements', make_date(EXTRACT(YEAR FROM CURRENT_DATE)::int, 10, 31)),
                    ('ADT-1', 'Auditor Appointment', make_date(EXTRACT(YEAR FROM CURRENT_DATE)::int, 10, 15)),
                    ('DIR-3 KYC', 'Director KYC', make_date(EXTRACT(YEAR FROM CURRENT_DATE)::int, 9, 30)),
                    ('MSME-1', 'MSME Payment dues', make_date(EXTRACT(YEAR FROM CURRENT_DATE)::int, 4, 30)),
                    ('MSME-1', 'MSME Payment dues', make_date(EXTRACT(YEAR FROM CURRENT_DATE)::int, 10, 31)),
                    ('DPT-3', 'Return of Deposits', make_date(EXTRACT(YEAR FROM CURRENT_DATE)::int, 6, 30)),
                    ('BEN-2', 'Beneficial Ownership', make_date(EXTRACT(YEAR FROM CURRENT_DATE)::int, 12, 31))
            ) AS seeded(form_number, form_description, due_date)
            WHERE NOT EXISTS (
                SELECT 1
                FROM statutory_filings sf
                WHERE sf.tenant_id = t.id
                  AND sf.form_number = seeded.form_number
                  AND sf.due_date = seeded.due_date
            )
            """
        )
    )


def upgrade() -> None:
    if not _table_exists("statutory_register_entries"):
        op.create_table(
            "statutory_register_entries",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("register_type", sa.String(length=50), nullable=False),
            sa.Column("entry_date", sa.Date(), nullable=False),
            sa.Column("entry_description", sa.Text(), nullable=False),
            sa.Column("folio_number", sa.String(length=100), nullable=True),
            sa.Column("amount", sa.Numeric(20, 2), nullable=True),
            sa.Column("currency", sa.String(length=3), nullable=True),
            sa.Column("reference_document", sa.Text(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _table_exists("statutory_filings"):
        op.create_table(
            "statutory_filings",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("form_number", sa.String(length=20), nullable=False),
            sa.Column("form_description", sa.String(length=300), nullable=False),
            sa.Column("due_date", sa.Date(), nullable=False),
            sa.Column("filed_date", sa.Date(), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'pending'")),
            sa.Column("filing_reference", sa.String(length=100), nullable=True),
            sa.Column("penalty_amount", sa.Numeric(20, 2), nullable=False, server_default=sa.text("0")),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _index_exists("idx_statutory_filings_tenant_due_status"):
        op.create_index("idx_statutory_filings_tenant_due_status", "statutory_filings", ["tenant_id", "due_date", "status"], unique=False)

    if _table_exists("statutory_filings"):
        op.execute(sa.text(append_only_function_sql()))
        op.execute(sa.text(drop_trigger_sql("statutory_filings")))
        op.execute(sa.text(create_trigger_sql("statutory_filings")))

    if _table_exists("statutory_register_entries"):
        _enable_rls("statutory_register_entries")
    if _table_exists("statutory_filings"):
        _enable_rls("statutory_filings")
        _seed_forms()


def downgrade() -> None:
    if _table_exists("statutory_filings"):
        op.execute(sa.text(drop_trigger_sql("statutory_filings")))
    if _table_exists("statutory_filings"):
        op.drop_table("statutory_filings")
    if _table_exists("statutory_register_entries"):
        op.drop_table("statutory_register_entries")
