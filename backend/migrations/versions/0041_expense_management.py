"""Expense management core cycle tables and policy defaults.

Revision ID: 0041_expense_management
Revises: 0040_working_capital
Create Date: 2026-03-23 00:20:00.000000
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from financeops.db.append_only import append_only_function_sql, create_trigger_sql, drop_trigger_sql

revision: str = "0041_expense_management"
down_revision: str | None = "0040_working_capital"
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


def _enable_rls_with_policies(table_name: str) -> None:
    op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
    if not _policy_exists(table_name, "tenant_isolation"):
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table_name} "
            "USING (tenant_id = COALESCE(NULLIF(current_setting('app.tenant_id', true), ''), NULLIF(current_setting('app.current_tenant_id', true), ''))::uuid)"
        )


def _seed_default_policies() -> None:
    bind = op.get_bind()
    tenant_rows = bind.execute(sa.text("SELECT id FROM iam_tenants")).fetchall()
    for row in tenant_rows:
        tenant_id = row[0]
        exists = bind.execute(
            sa.text("SELECT 1 FROM expense_policies WHERE tenant_id = :tenant_id LIMIT 1"),
            {"tenant_id": tenant_id},
        ).scalar_one_or_none()
        if exists:
            continue
        bind.execute(
            sa.text(
                """
                INSERT INTO expense_policies (
                    id, tenant_id, meal_limit_per_day, travel_limit_per_night,
                    receipt_required_above, auto_approve_below,
                    weekend_flag_enabled, round_number_flag_enabled,
                    personal_merchant_keywords, created_at, updated_at
                ) VALUES (
                    gen_random_uuid(), :tenant_id, 2000, 8000,
                    500, 0, true, true,
                    CAST(:keywords AS jsonb), now(), now()
                )
                """
            ),
            {
                "tenant_id": tenant_id,
                "keywords": json.dumps(["swiggy", "zomato", "amazon"]),
            },
        )


def upgrade() -> None:
    if not _table_exists("expense_policies"):
        op.create_table(
            "expense_policies",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False, server_default=sa.text("gen_random_uuid()")),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
            sa.Column("meal_limit_per_day", sa.Numeric(10, 2), nullable=False, server_default=sa.text("2000")),
            sa.Column("travel_limit_per_night", sa.Numeric(10, 2), nullable=False, server_default=sa.text("8000")),
            sa.Column("receipt_required_above", sa.Numeric(10, 2), nullable=False, server_default=sa.text("500")),
            sa.Column("auto_approve_below", sa.Numeric(10, 2), nullable=False, server_default=sa.text("0")),
            sa.Column("weekend_flag_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("round_number_flag_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("personal_merchant_keywords", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        )

    if not _table_exists("expense_claims"):
        op.create_table(
            "expense_claims",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False, server_default=sa.text("gen_random_uuid()")),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("submitted_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("iam_users.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("period", sa.String(length=7), nullable=False),
            sa.Column("claim_date", sa.Date(), nullable=False),
            sa.Column("vendor_name", sa.String(length=300), nullable=False),
            sa.Column("vendor_gstin", sa.String(length=20), nullable=True),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("category", sa.String(length=50), nullable=False),
            sa.Column("amount", sa.Numeric(20, 2), nullable=False),
            sa.Column("currency", sa.String(length=3), nullable=False, server_default=sa.text("'INR'")),
            sa.Column("amount_inr", sa.Numeric(20, 2), nullable=False),
            sa.Column("receipt_url", sa.Text(), nullable=True),
            sa.Column("gst_amount", sa.Numeric(20, 2), nullable=False, server_default=sa.text("0")),
            sa.Column("itc_eligible", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("status", sa.String(length=30), nullable=False, server_default=sa.text("'submitted'")),
            sa.Column("policy_violation_type", sa.String(length=50), nullable=True),
            sa.Column("policy_violation_requires_justification", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("justification", sa.Text(), nullable=True),
            sa.Column("manager_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("manager_approved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("finance_approved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("gl_account_code", sa.String(length=50), nullable=True),
            sa.Column("gl_account_name", sa.String(length=200), nullable=True),
            sa.Column("cost_centre", sa.String(length=100), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.CheckConstraint(
                "category IN ('meals','travel','accommodation','office_supplies','professional_fees','other')",
                name="ck_expense_claims_category",
            ),
            sa.CheckConstraint(
                "status IN ('submitted','policy_checked','approved','rejected','gl_coded','paid','cancelled')",
                name="ck_expense_claims_status",
            ),
            sa.CheckConstraint(
                "policy_violation_type IS NULL OR policy_violation_type IN ('none','soft_limit','hard_limit','receipt_missing','personal_merchant','duplicate','weekend','round_number')",
                name="ck_expense_claims_violation",
            ),
        )

    if not _table_exists("expense_approvals"):
        op.create_table(
            "expense_approvals",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False, server_default=sa.text("gen_random_uuid()")),
            sa.Column("claim_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("expense_claims.id", ondelete="CASCADE"), nullable=False),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("approver_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("iam_users.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("approver_role", sa.String(length=50), nullable=False),
            sa.Column("action", sa.String(length=20), nullable=False),
            sa.Column("comments", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.CheckConstraint("action IN ('approved','rejected','returned')", name="ck_expense_approvals_action"),
        )

    if not _index_exists("idx_expense_claims_tenant_user_period"):
        op.execute("CREATE INDEX idx_expense_claims_tenant_user_period ON expense_claims (tenant_id, submitted_by, period)")
    if not _index_exists("idx_expense_claims_tenant_status"):
        op.execute("CREATE INDEX idx_expense_claims_tenant_status ON expense_claims (tenant_id, status)")
    if not _index_exists("idx_expense_approvals_claim"):
        op.execute("CREATE INDEX idx_expense_approvals_claim ON expense_approvals (claim_id)")
    if not _index_exists("idx_expense_policies_tenant"):
        op.execute("CREATE UNIQUE INDEX idx_expense_policies_tenant ON expense_policies (tenant_id)")

    _seed_default_policies()

    for table_name in ("expense_policies", "expense_claims", "expense_approvals"):
        if _table_exists(table_name):
            _enable_rls_with_policies(table_name)

    for append_only_table in ("expense_claims", "expense_approvals"):
        if _table_exists(append_only_table):
            op.execute(append_only_function_sql())
            op.execute(drop_trigger_sql(append_only_table))
            op.execute(create_trigger_sql(append_only_table))


def downgrade() -> None:
    for table_name in ("expense_approvals", "expense_claims"):
        if _table_exists(table_name):
            op.execute(drop_trigger_sql(table_name))

    if _index_exists("idx_expense_approvals_claim") and _table_exists("expense_approvals"):
        op.drop_index("idx_expense_approvals_claim", table_name="expense_approvals")
    if _index_exists("idx_expense_claims_tenant_status") and _table_exists("expense_claims"):
        op.drop_index("idx_expense_claims_tenant_status", table_name="expense_claims")
    if _index_exists("idx_expense_claims_tenant_user_period") and _table_exists("expense_claims"):
        op.drop_index("idx_expense_claims_tenant_user_period", table_name="expense_claims")
    if _index_exists("idx_expense_policies_tenant") and _table_exists("expense_policies"):
        op.drop_index("idx_expense_policies_tenant", table_name="expense_policies")

    if _table_exists("expense_approvals"):
        op.drop_table("expense_approvals")
    if _table_exists("expense_claims"):
        op.drop_table("expense_claims")
    if _table_exists("expense_policies"):
        op.drop_table("expense_policies")

