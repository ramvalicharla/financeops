"""phase12_saas_platformization_layer

Revision ID: 0109_saas_platformization_layer
Revises: 0108_industry_modules_layer
Create Date: 2026-04-02
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from financeops.db.append_only import append_only_function_sql, create_trigger_sql, drop_trigger_sql

revision: str = "0109_saas_platformization_layer"
down_revision: str | None = "0108_industry_modules_layer"
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


def _drop_rls_policy(table_name: str) -> None:
    op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table_name}")


def upgrade() -> None:
    op.add_column("billing_plans", sa.Column("name", sa.String(length=128), nullable=True))
    op.add_column("billing_plans", sa.Column("pricing_type", sa.String(length=16), nullable=True))
    op.add_column("billing_plans", sa.Column("price", sa.Numeric(20, 6), nullable=True))
    op.add_column("billing_plans", sa.Column("currency", sa.String(length=3), nullable=True))
    op.create_check_constraint(
        "ck_billing_plans_pricing_type",
        "billing_plans",
        "pricing_type IS NULL OR pricing_type IN ('flat','tiered','usage','hybrid')",
    )

    op.execute(
        """
        UPDATE billing_plans
        SET
          name = COALESCE(name, initcap(plan_tier) || ' ' || initcap(billing_cycle)),
          pricing_type = COALESCE(pricing_type, 'flat'),
          price = COALESCE(price, base_price_usd),
          currency = COALESCE(currency, 'USD')
        """
    )

    op.add_column("tenant_subscriptions", sa.Column("start_date", sa.Date(), nullable=True))
    op.add_column("tenant_subscriptions", sa.Column("end_date", sa.Date(), nullable=True))
    op.add_column("tenant_subscriptions", sa.Column("trial_end_date", sa.Date(), nullable=True))
    op.add_column(
        "tenant_subscriptions",
        sa.Column("auto_renew", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.execute(
        """
        UPDATE tenant_subscriptions
        SET
          start_date = COALESCE(start_date, current_period_start),
          end_date = COALESCE(end_date, current_period_end),
          trial_end_date = COALESCE(trial_end_date, trial_end),
          auto_renew = COALESCE(auto_renew, NOT cancel_at_period_end)
        """
    )

    op.add_column("billing_invoices", sa.Column("amount", sa.Numeric(20, 6), nullable=True))
    op.add_column("billing_invoices", sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("billing_invoices", sa.Column("due_at", sa.DateTime(timezone=True), nullable=True))
    op.execute(
        """
        UPDATE billing_invoices
        SET
          amount = COALESCE(amount, total),
          issued_at = COALESCE(issued_at, created_at)
        """
    )

    _create(
        "billing_payments",
        [
            sa.Column("invoice_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("amount", sa.Numeric(20, 6), nullable=False),
            sa.Column("payment_status", sa.String(length=32), nullable=False),
            sa.Column("provider_reference", sa.String(length=255), nullable=False),
            sa.Column("provider", sa.String(length=32), nullable=True),
            sa.Column(
                "metadata",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
        ],
        sa.ForeignKeyConstraint(["invoice_id"], ["billing_invoices.id"], ondelete="RESTRICT"),
        sa.CheckConstraint(
            "payment_status IN ('pending','succeeded','failed','refunded')",
            name="ck_billing_payments_status",
        ),
        sa.UniqueConstraint("tenant_id", "provider_reference", name="uq_billing_payments_provider_ref"),
    )
    op.create_index(
        "idx_billing_payments_tenant_invoice",
        "billing_payments",
        ["tenant_id", "invoice_id", "created_at"],
    )

    _create(
        "billing_entitlements",
        [
            sa.Column("plan_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("feature_name", sa.String(length=128), nullable=False),
            sa.Column("access_type", sa.String(length=16), nullable=False),
            sa.Column("limit_value", sa.BigInteger(), nullable=True),
            sa.Column(
                "metadata",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        ],
        sa.ForeignKeyConstraint(["plan_id"], ["billing_plans.id"], ondelete="RESTRICT"),
        sa.CheckConstraint(
            "access_type IN ('boolean','limit','quota')",
            name="ck_billing_entitlements_access_type",
        ),
    )
    op.create_index(
        "idx_billing_entitlements_plan_feature",
        "billing_entitlements",
        ["tenant_id", "plan_id", "feature_name", "created_at"],
    )
    op.execute(
        """
        INSERT INTO billing_entitlements (
            id, tenant_id, chain_hash, previous_hash, created_at,
            plan_id, feature_name, access_type, limit_value, metadata, is_active
        )
        SELECT
            gen_random_uuid(),
            bp.tenant_id,
            repeat('0', 64),
            repeat('0', 64),
            now(),
            bp.id,
            seeded.feature_name,
            seeded.access_type,
            seeded.limit_value,
            seeded.metadata::jsonb,
            true
        FROM billing_plans bp
        CROSS JOIN LATERAL (
            VALUES
                ('analytics', 'boolean', 1::bigint, '{}'),
                (
                    'ai_cfo',
                    'quota',
                    CASE
                        WHEN bp.plan_tier = 'starter' THEN 200::bigint
                        WHEN bp.plan_tier = 'professional' THEN 1000::bigint
                        ELSE NULL::bigint
                    END,
                    '{"price_per_unit":"0"}'
                ),
                (
                    'erp_integration',
                    'limit',
                    CASE
                        WHEN bp.plan_tier = 'starter' THEN 1::bigint
                        WHEN bp.plan_tier = 'professional' THEN 5::bigint
                        ELSE NULL::bigint
                    END,
                    '{"price_per_unit":"0"}'
                ),
                (
                    'industry_modules',
                    'boolean',
                    CASE
                        WHEN bp.plan_tier = 'starter' THEN 0::bigint
                        ELSE 1::bigint
                    END,
                    '{}'
                )
        ) AS seeded(feature_name, access_type, limit_value, metadata)
        """
    )

    _create(
        "billing_tenant_entitlements",
        [
            sa.Column("feature_name", sa.String(length=128), nullable=False),
            sa.Column("access_type", sa.String(length=16), nullable=False),
            sa.Column("effective_limit", sa.BigInteger(), nullable=True),
            sa.Column("source", sa.String(length=16), nullable=False, server_default=sa.text("'plan'")),
            sa.Column("source_reference_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column(
                "metadata",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        ],
        sa.CheckConstraint(
            "source IN ('plan','override')",
            name="ck_billing_tenant_entitlements_source",
        ),
    )
    op.create_index(
        "idx_billing_tenant_entitlements_feature",
        "billing_tenant_entitlements",
        ["tenant_id", "feature_name", "created_at"],
    )

    _create(
        "billing_usage_events",
        [
            sa.Column("feature_name", sa.String(length=128), nullable=False),
            sa.Column("usage_quantity", sa.BigInteger(), nullable=False),
            sa.Column(
                "event_time",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column("period_start", sa.Date(), nullable=True),
            sa.Column("period_end", sa.Date(), nullable=True),
            sa.Column("reference_type", sa.String(length=64), nullable=True),
            sa.Column("reference_id", sa.String(length=255), nullable=True),
            sa.Column(
                "metadata",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
        ],
    )
    op.create_index(
        "idx_billing_usage_events_feature_time",
        "billing_usage_events",
        ["tenant_id", "feature_name", "event_time"],
    )

    _create(
        "billing_usage_aggregates",
        [
            sa.Column("feature_name", sa.String(length=128), nullable=False),
            sa.Column("period_start", sa.Date(), nullable=False),
            sa.Column("period_end", sa.Date(), nullable=False),
            sa.Column("total_usage", sa.BigInteger(), nullable=False),
            sa.Column("last_event_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column(
                "metadata",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
        ],
        sa.ForeignKeyConstraint(["last_event_id"], ["billing_usage_events.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "idx_billing_usage_aggregates_period",
        "billing_usage_aggregates",
        ["tenant_id", "feature_name", "period_start", "period_end"],
    )

    new_tables = [
        "billing_payments",
        "billing_entitlements",
        "billing_tenant_entitlements",
        "billing_usage_events",
        "billing_usage_aggregates",
    ]
    for table_name in new_tables:
        _enable_rls(table_name)

    op.execute(append_only_function_sql())
    for table_name in new_tables:
        op.execute(drop_trigger_sql(table_name))
        op.execute(create_trigger_sql(table_name))


def downgrade() -> None:
    new_tables = [
        "billing_usage_aggregates",
        "billing_usage_events",
        "billing_tenant_entitlements",
        "billing_entitlements",
        "billing_payments",
    ]

    for table_name in new_tables:
        op.execute(drop_trigger_sql(table_name))
        _drop_rls_policy(table_name)
        op.drop_table(table_name)

    op.drop_column("billing_invoices", "due_at")
    op.drop_column("billing_invoices", "issued_at")
    op.drop_column("billing_invoices", "amount")

    op.drop_column("tenant_subscriptions", "auto_renew")
    op.drop_column("tenant_subscriptions", "trial_end_date")
    op.drop_column("tenant_subscriptions", "end_date")
    op.drop_column("tenant_subscriptions", "start_date")

    op.drop_constraint("ck_billing_plans_pricing_type", "billing_plans", type_="check")
    op.drop_column("billing_plans", "currency")
    op.drop_column("billing_plans", "price")
    op.drop_column("billing_plans", "pricing_type")
    op.drop_column("billing_plans", "name")
