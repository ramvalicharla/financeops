"""Phase 5 Payment Module

Revision ID: 0027_payment_module
Revises: 0026_phase4_erp_sync
Create Date: 2026-03-12 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from financeops.db.append_only import append_only_function_sql, create_trigger_sql, drop_trigger_sql

revision: str = "0027_payment_module"
down_revision: str | None = "0026_phase4_erp_sync"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _base_cols() -> list[sa.Column]:
    return [
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    ]


def _create(name: str, extra: list[sa.Column], *constraints: sa.Constraint) -> None:
    op.create_table(name, *_base_cols(), *extra, sa.PrimaryKeyConstraint("id"), *constraints)


def _enable_rls(table_name: str) -> None:
    op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation ON {table_name} "
        "USING (tenant_id = COALESCE(current_setting('app.tenant_id', true), current_setting('app.current_tenant_id', true))::uuid)"
    )


def upgrade() -> None:
    _create(
        "billing_plans",
        [
            sa.Column("plan_tier", sa.String(length=32), nullable=False),
            sa.Column("billing_cycle", sa.String(length=16), nullable=False),
            sa.Column("base_price_inr", sa.Numeric(20, 6), nullable=False),
            sa.Column("base_price_usd", sa.Numeric(20, 6), nullable=False),
            sa.Column("included_credits", sa.Integer(), nullable=False),
            sa.Column("max_entities", sa.Integer(), nullable=False),
            sa.Column("max_connectors", sa.Integer(), nullable=False),
            sa.Column("max_users", sa.Integer(), nullable=False),
            sa.Column(
                "modules_enabled",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column("trial_days", sa.Integer(), nullable=False),
            sa.Column("annual_discount_pct", sa.Numeric(20, 6), nullable=False, server_default="0"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("valid_from", sa.Date(), nullable=False),
            sa.Column("valid_until", sa.Date(), nullable=True),
        ],
        sa.CheckConstraint("plan_tier IN ('starter','professional','enterprise')", name="ck_billing_plans_tier"),
        sa.CheckConstraint("billing_cycle IN ('monthly','annual')", name="ck_billing_plans_cycle"),
        sa.CheckConstraint("annual_discount_pct >= 0", name="ck_billing_plans_discount_non_negative"),
    )
    op.create_index("idx_billing_plans_tenant_active", "billing_plans", ["tenant_id", "is_active", "created_at"])

    _create(
        "tenant_subscriptions",
        [
            sa.Column("plan_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("provider", sa.String(length=32), nullable=False),
            sa.Column("provider_subscription_id", sa.String(length=255), nullable=False),
            sa.Column("provider_customer_id", sa.String(length=255), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("billing_cycle", sa.String(length=16), nullable=False),
            sa.Column("current_period_start", sa.Date(), nullable=False),
            sa.Column("current_period_end", sa.Date(), nullable=False),
            sa.Column("trial_start", sa.Date(), nullable=True),
            sa.Column("trial_end", sa.Date(), nullable=True),
            sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("cancel_at_period_end", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("onboarding_mode", sa.String(length=32), nullable=False),
            sa.Column("billing_country", sa.String(length=2), nullable=False),
            sa.Column("billing_currency", sa.String(length=3), nullable=False),
            sa.Column(
                "metadata",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
        ],
        sa.ForeignKeyConstraint(["plan_id"], ["billing_plans.id"], ondelete="RESTRICT"),
        sa.CheckConstraint(
            "status IN ('trialing','active','past_due','grace_period','suspended','cancelled','incomplete')",
            name="ck_tenant_subscriptions_status",
        ),
        sa.CheckConstraint("billing_cycle IN ('monthly','annual')", name="ck_tenant_subscriptions_cycle"),
        sa.CheckConstraint("onboarding_mode IN ('self_serve','sales_assisted')", name="ck_tenant_subscriptions_onboarding_mode"),
    )
    op.create_index(
        "idx_tenant_subscriptions_current",
        "tenant_subscriptions",
        ["tenant_id", "status", "current_period_end", "created_at"],
    )

    _create(
        "subscription_events",
        [
            sa.Column("subscription_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("event_type", sa.String(length=64), nullable=False),
            sa.Column("from_plan_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("to_plan_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("from_status", sa.String(length=32), nullable=True),
            sa.Column("to_status", sa.String(length=32), nullable=False),
            sa.Column("provider_event_id", sa.String(length=255), nullable=True),
            sa.Column(
                "metadata",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
        ],
        sa.ForeignKeyConstraint(["subscription_id"], ["tenant_subscriptions.id"], ondelete="RESTRICT"),
    )
    op.create_index(
        "idx_subscription_events_subscription",
        "subscription_events",
        ["tenant_id", "subscription_id", "created_at"],
    )

    _create(
        "billing_invoices",
        [
            sa.Column("subscription_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("provider_invoice_id", sa.String(length=255), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("currency", sa.String(length=3), nullable=False),
            sa.Column("subtotal", sa.Numeric(20, 6), nullable=False),
            sa.Column("tax", sa.Numeric(20, 6), nullable=False, server_default="0"),
            sa.Column("total", sa.Numeric(20, 6), nullable=False),
            sa.Column("credits_applied", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("due_date", sa.Date(), nullable=False),
            sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("invoice_pdf_url", sa.String(length=512), nullable=True),
            sa.Column(
                "line_items",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'[]'::jsonb"),
            ),
        ],
        sa.ForeignKeyConstraint(["subscription_id"], ["tenant_subscriptions.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("status IN ('draft','open','paid','void','uncollectible')", name="ck_billing_invoices_status"),
    )
    op.create_index(
        "idx_billing_invoices_tenant",
        "billing_invoices",
        ["tenant_id", "subscription_id", "status", "created_at"],
    )

    _create(
        "payment_methods",
        [
            sa.Column("provider", sa.String(length=32), nullable=False),
            sa.Column("provider_payment_method_id", sa.String(length=255), nullable=False),
            sa.Column("type", sa.String(length=32), nullable=False),
            sa.Column("last4", sa.String(length=8), nullable=True),
            sa.Column("brand", sa.String(length=64), nullable=True),
            sa.Column("expiry_month", sa.Integer(), nullable=True),
            sa.Column("expiry_year", sa.Integer(), nullable=True),
            sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column(
                "billing_details",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
        ],
    )
    op.create_index(
        "idx_payment_methods_tenant",
        "payment_methods",
        ["tenant_id", "provider", "is_default", "created_at"],
    )

    _create(
        "credit_ledger",
        [
            sa.Column("transaction_type", sa.String(length=32), nullable=False),
            sa.Column("credits_delta", sa.Integer(), nullable=False),
            sa.Column("credits_balance_after", sa.Integer(), nullable=False),
            sa.Column("reference_id", sa.String(length=255), nullable=True),
            sa.Column("reference_type", sa.String(length=64), nullable=True),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        ],
        sa.CheckConstraint(
            "transaction_type IN ('plan_allocation','top_up_purchase','consumption','expiry','refund','adjustment')",
            name="ck_credit_ledger_transaction_type",
        ),
    )
    op.create_index("idx_credit_ledger_tenant_created", "credit_ledger", ["tenant_id", "created_at"])

    _create(
        "credit_top_ups",
        [
            sa.Column("credits_purchased", sa.Integer(), nullable=False),
            sa.Column("amount_charged", sa.Numeric(20, 6), nullable=False),
            sa.Column("currency", sa.String(length=3), nullable=False),
            sa.Column("provider", sa.String(length=32), nullable=False),
            sa.Column("provider_payment_id", sa.String(length=255), nullable=False),
            sa.Column("invoice_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False),
        ],
        sa.ForeignKeyConstraint(["invoice_id"], ["billing_invoices.id"], ondelete="SET NULL"),
        sa.CheckConstraint("status IN ('pending','completed','failed','refunded')", name="ck_credit_top_ups_status"),
        sa.UniqueConstraint("tenant_id", "provider_payment_id", name="uq_credit_top_ups_provider_payment"),
    )
    op.create_index("idx_credit_top_ups_tenant", "credit_top_ups", ["tenant_id", "status", "created_at"])

    _create(
        "webhook_events",
        [
            sa.Column("provider", sa.String(length=32), nullable=False),
            sa.Column("provider_event_id", sa.String(length=255), nullable=False),
            sa.Column("event_type", sa.String(length=128), nullable=False),
            sa.Column(
                "payload",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column("processed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("processing_error", sa.Text(), nullable=True),
        ],
        sa.UniqueConstraint("tenant_id", "provider", "provider_event_id", name="uq_webhook_events_provider_event"),
    )
    op.create_index("idx_webhook_events_tenant", "webhook_events", ["tenant_id", "provider", "processed", "created_at"])

    _create(
        "grace_period_logs",
        [
            sa.Column("subscription_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("grace_period_start", sa.DateTime(timezone=True), nullable=False),
            sa.Column("grace_period_end", sa.DateTime(timezone=True), nullable=False),
            sa.Column("grace_period_days", sa.Integer(), nullable=False, server_default="7"),
            sa.Column("reason", sa.String(length=64), nullable=False),
            sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("resolved_by", sa.String(length=255), nullable=True),
            sa.Column("resolution", sa.String(length=64), nullable=True),
        ],
        sa.ForeignKeyConstraint(["subscription_id"], ["tenant_subscriptions.id"], ondelete="RESTRICT"),
    )
    op.create_index(
        "idx_grace_period_logs_tenant",
        "grace_period_logs",
        ["tenant_id", "subscription_id", "grace_period_end", "created_at"],
    )

    _create(
        "proration_records",
        [
            sa.Column("subscription_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("from_plan_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("to_plan_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("proration_date", sa.Date(), nullable=False),
            sa.Column("credit_amount", sa.Numeric(20, 6), nullable=False, server_default="0"),
            sa.Column("debit_amount", sa.Numeric(20, 6), nullable=False, server_default="0"),
            sa.Column("currency", sa.String(length=3), nullable=False),
            sa.Column("net_adjustment", sa.Numeric(20, 6), nullable=False, server_default="0"),
            sa.Column("applied_to_invoice_id", postgresql.UUID(as_uuid=True), nullable=True),
        ],
        sa.ForeignKeyConstraint(["subscription_id"], ["tenant_subscriptions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["applied_to_invoice_id"], ["billing_invoices.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "idx_proration_records_tenant",
        "proration_records",
        ["tenant_id", "subscription_id", "proration_date", "created_at"],
    )

    tables = [
        "billing_plans",
        "tenant_subscriptions",
        "subscription_events",
        "billing_invoices",
        "payment_methods",
        "credit_ledger",
        "credit_top_ups",
        "webhook_events",
        "grace_period_logs",
        "proration_records",
    ]

    for table_name in tables:
        _enable_rls(table_name)

    op.execute(append_only_function_sql())
    for table_name in tables:
        op.execute(drop_trigger_sql(table_name))
        op.execute(create_trigger_sql(table_name))

    op.execute(
        """
        INSERT INTO cp_module_registry (
          id, module_code, module_name, engine_context, is_financial_impacting, is_active, created_at
        )
        VALUES (
          '31531a68-a0a1-4b0e-93e6-a753f58ef8e4'::uuid,
          'payment',
          'Payment Module',
          'finance',
          true,
          true,
          now()
        )
        ON CONFLICT (module_code) DO NOTHING
        """
    )


def downgrade() -> None:
    tables = [
        "proration_records",
        "grace_period_logs",
        "webhook_events",
        "credit_top_ups",
        "credit_ledger",
        "payment_methods",
        "billing_invoices",
        "subscription_events",
        "tenant_subscriptions",
        "billing_plans",
    ]

    for table_name in tables:
        op.execute(drop_trigger_sql(table_name))
        op.drop_table(table_name)

    op.execute("DELETE FROM cp_module_registry WHERE module_code = 'payment'")
