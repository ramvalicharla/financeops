from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from financeops.db.append_only import APPEND_ONLY_TABLES, append_only_function_sql, create_trigger_sql, drop_trigger_sql
from financeops.db.models.payment import BillingPlan
from financeops.modules.payment.domain.enums import BillingCycle, PlanTier
from financeops.services.audit_writer import AuditWriter


PAYMENT_TABLES = [
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


@pytest.mark.asyncio
@pytest.mark.integration
async def test_payment_tables_registered_as_append_only() -> None:
    assert set(PAYMENT_TABLES).issubset(set(APPEND_ONLY_TABLES))


@pytest.mark.asyncio
@pytest.mark.integration
async def test_append_only_rejects_update_for_billing_plan(async_session) -> None:
    await async_session.execute(text(append_only_function_sql()))
    await async_session.execute(text(drop_trigger_sql("billing_plans")))
    await async_session.execute(text(create_trigger_sql("billing_plans")))
    tenant_id = uuid.uuid4()
    row = await AuditWriter.insert_financial_record(
        async_session,
        model_class=BillingPlan,
        tenant_id=tenant_id,
        record_data={"plan_tier": PlanTier.STARTER.value, "billing_cycle": BillingCycle.MONTHLY.value},
        values={
            "plan_tier": PlanTier.STARTER.value,
            "billing_cycle": BillingCycle.MONTHLY.value,
            "base_price_inr": Decimal("99.00"),
            "base_price_usd": Decimal("99.00"),
            "included_credits": 100,
            "max_entities": 3,
            "max_connectors": 3,
            "max_users": 3,
            "modules_enabled": {"payment": True},
            "trial_days": 14,
            "annual_discount_pct": Decimal("10.00"),
            "is_active": True,
            "valid_from": datetime.now(UTC).date(),
            "valid_until": None,
        },
    )

    with pytest.raises(DBAPIError):
        await async_session.execute(
            text("UPDATE billing_plans SET is_active = false WHERE id = :id"),
            {"id": str(row.id)},
        )
        await async_session.flush()
