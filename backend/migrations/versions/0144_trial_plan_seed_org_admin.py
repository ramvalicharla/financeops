"""add trial plan tier, seed 4 plans, add org_admin role

Revision ID: 0144_trial_plan_seed
Revises: 0143_tenant_created_idx
Create Date: 2026-04-24 00:00:00.000000
"""

from __future__ import annotations

import uuid
from datetime import date

from alembic import op
import sqlalchemy as sa


revision = "0144_trial_plan_seed"
down_revision = "0143_tenant_created_idx"
branch_labels = None
depends_on = None

# Stable UUIDs so re-runs are idempotent
_PLAN_IDS = {
    "trial":        "00000000-0000-0000-0000-000000000001",
    "starter":      "00000000-0000-0000-0000-000000000002",
    "professional": "00000000-0000-0000-0000-000000000003",
    "enterprise":   "00000000-0000-0000-0000-000000000004",
}

# Sentinel for "unlimited" on non-nullable integer columns
_UNLIMITED = -1

_VALID_FROM = date(2026, 1, 1).isoformat()
_GENESIS_HASH = "0" * 64


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Drop old tier check constraint and replace with one that includes 'trial'
    op.drop_constraint("ck_billing_plans_tier", "billing_plans")
    op.create_check_constraint(
        "ck_billing_plans_tier",
        "billing_plans",
        "plan_tier IN ('trial','starter','professional','enterprise')",
    )

    # 2. Add org_admin to the iam_users role enum
    #    PostgreSQL enums require ALTER TYPE; Alembic exposes execute() for raw DDL.
    #    The type is named user_role_enum (defined in 0001_initial_schema.py).
    op.execute(
        sa.text(
            "DO $$ BEGIN "
            "  IF NOT EXISTS (SELECT 1 FROM pg_enum e JOIN pg_type t ON t.oid = e.enumtypid "
            "    WHERE t.typname = 'user_role_enum' AND e.enumlabel = 'org_admin') THEN "
            "    ALTER TYPE user_role_enum ADD VALUE 'org_admin'; "
            "  END IF; "
            "END $$"
        )
    )

    # 3. Seed the 4 canonical plans (INSERT ... ON CONFLICT DO NOTHING)
    plans = [
        {
            "id":                   _PLAN_IDS["trial"],
            "tenant_id":            "00000000-0000-0000-0000-000000000000",
            "plan_tier":            "trial",
            "name":                 "Trial",
            "billing_cycle":        "monthly",
            "base_price_usd":       "0.000000",
            "base_price_inr":       "0.000000",
            "price":                "0.000000",
            "currency":             "USD",
            "pricing_type":         "flat",
            "included_credits":     100,
            "trial_days":           14,
            "max_users":            3,
            "max_entities":         1,
            "max_connectors":       0,
            "modules_enabled":      "{}",
            "annual_discount_pct":  "0.000000",
            "is_active":            True,
            "valid_from":           _VALID_FROM,
            "valid_until":          None,
            "chain_hash":           _GENESIS_HASH,
            "previous_hash":        _GENESIS_HASH,
        },
        {
            "id":                   _PLAN_IDS["starter"],
            "tenant_id":            "00000000-0000-0000-0000-000000000000",
            "plan_tier":            "starter",
            "name":                 "Starter",
            "billing_cycle":        "monthly",
            "base_price_usd":       "29.000000",
            "base_price_inr":       "2499.000000",
            "price":                "29.000000",
            "currency":             "USD",
            "pricing_type":         "flat",
            "included_credits":     500,
            "trial_days":           0,
            "max_users":            5,
            "max_entities":         2,
            "max_connectors":       5,
            "modules_enabled":      "{}",
            "annual_discount_pct":  "0.000000",
            "is_active":            True,
            "valid_from":           _VALID_FROM,
            "valid_until":          None,
            "chain_hash":           _GENESIS_HASH,
            "previous_hash":        _GENESIS_HASH,
        },
        {
            "id":                   _PLAN_IDS["professional"],
            "tenant_id":            "00000000-0000-0000-0000-000000000000",
            "plan_tier":            "professional",
            "name":                 "Professional",
            "billing_cycle":        "monthly",
            "base_price_usd":       "99.000000",
            "base_price_inr":       "7999.000000",
            "price":                "99.000000",
            "currency":             "USD",
            "pricing_type":         "flat",
            "included_credits":     2000,
            "trial_days":           0,
            "max_users":            20,
            "max_entities":         10,
            "max_connectors":       20,
            "modules_enabled":      "{}",
            "annual_discount_pct":  "0.000000",
            "is_active":            True,
            "valid_from":           _VALID_FROM,
            "valid_until":          None,
            "chain_hash":           _GENESIS_HASH,
            "previous_hash":        _GENESIS_HASH,
        },
        {
            "id":                   _PLAN_IDS["enterprise"],
            "tenant_id":            "00000000-0000-0000-0000-000000000000",
            "plan_tier":            "enterprise",
            "name":                 "Enterprise",
            "billing_cycle":        "monthly",
            "base_price_usd":       "299.000000",
            "base_price_inr":       "24999.000000",
            "price":                "299.000000",
            "currency":             "USD",
            "pricing_type":         "flat",
            "included_credits":     10000,
            "trial_days":           0,
            "max_users":            _UNLIMITED,
            "max_entities":         _UNLIMITED,
            "max_connectors":       _UNLIMITED,
            "modules_enabled":      "{}",
            "annual_discount_pct":  "0.000000",
            "is_active":            True,
            "valid_from":           _VALID_FROM,
            "valid_until":          None,
            "chain_hash":           _GENESIS_HASH,
            "previous_hash":        _GENESIS_HASH,
        },
    ]

    for plan in plans:
        conn.execute(
            sa.text(
                """
                INSERT INTO billing_plans (
                    id, tenant_id, plan_tier, name, billing_cycle,
                    base_price_usd, base_price_inr, price, currency, pricing_type,
                    included_credits, trial_days,
                    max_users, max_entities, max_connectors,
                    modules_enabled, annual_discount_pct, is_active,
                    valid_from, valid_until,
                    chain_hash, previous_hash, created_at
                )
                VALUES (
                    CAST(:id AS uuid), CAST(:tenant_id AS uuid), :plan_tier, :name, :billing_cycle,
                    :base_price_usd, :base_price_inr, :price, :currency, :pricing_type,
                    :included_credits, :trial_days,
                    :max_users, :max_entities, :max_connectors,
                    CAST(:modules_enabled AS jsonb), :annual_discount_pct, :is_active,
                    CAST(:valid_from AS date), :valid_until,
                    :chain_hash, :previous_hash, now()
                )
                ON CONFLICT (id) DO NOTHING
                """
            ),
            plan,
        )


def downgrade() -> None:
    conn = op.get_bind()

    # Remove seeded plans
    for plan_id in _PLAN_IDS.values():
        conn.execute(
            sa.text("DELETE FROM billing_plans WHERE id = CAST(:id AS uuid)"),
            {"id": plan_id},
        )

    # Restore original tier constraint (without 'trial')
    op.drop_constraint("ck_billing_plans_tier", "billing_plans")
    op.create_check_constraint(
        "ck_billing_plans_tier",
        "billing_plans",
        "plan_tier IN ('starter','professional','enterprise')",
    )

    # Note: PostgreSQL does not support DROP VALUE from an enum type.
    # org_admin must be removed manually if needed.
