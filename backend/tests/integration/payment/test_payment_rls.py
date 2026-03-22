from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from financeops.db.rls import set_tenant_context
from financeops.modules.payment.domain.enums import BillingCycle, PlanTier
from tests.integration.payment.helpers import create_plan


@pytest.mark.asyncio
@pytest.mark.integration
async def test_tenant_rls_blocks_cross_tenant_visibility_for_billing_plans(async_session) -> None:
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()

    await async_session.execute(
        text(
            """
            DO $$
            BEGIN
              CREATE ROLE rls_payment_probe NOLOGIN NOSUPERUSER NOBYPASSRLS;
            EXCEPTION
              WHEN duplicate_object THEN NULL;
            END $$;
            """
        )
    )
    await async_session.execute(text("GRANT USAGE ON SCHEMA public TO rls_payment_probe"))
    await async_session.execute(text("GRANT SELECT, INSERT ON billing_plans TO rls_payment_probe"))
    await async_session.execute(text("ALTER TABLE billing_plans ENABLE ROW LEVEL SECURITY"))
    await async_session.execute(text("ALTER TABLE billing_plans FORCE ROW LEVEL SECURITY"))
    await async_session.execute(text("DROP POLICY IF EXISTS tenant_isolation ON billing_plans"))
    await async_session.execute(
        text(
            """
            CREATE POLICY tenant_isolation ON billing_plans
            USING (
                tenant_id = COALESCE(
                    current_setting('app.tenant_id', true),
                    current_setting('app.current_tenant_id', true)
                )::uuid
            )
            """
        )
    )

    await set_tenant_context(async_session, str(tenant_a))
    plan_a = await create_plan(
        async_session=async_session,
        tenant_id=tenant_a,
        plan_tier=PlanTier.STARTER,
        billing_cycle=BillingCycle.MONTHLY,
        price="99.00",
    )
    await set_tenant_context(async_session, str(tenant_b))
    plan_b = await create_plan(
        async_session=async_session,
        tenant_id=tenant_b,
        plan_tier=PlanTier.PROFESSIONAL,
        billing_cycle=BillingCycle.MONTHLY,
        price="199.00",
    )

    await async_session.execute(text("SET ROLE rls_payment_probe"))
    try:
        await set_tenant_context(async_session, str(tenant_a))
        own_visible = (
            await async_session.execute(
                text("SELECT COUNT(*) FROM billing_plans WHERE id = :id"),
                {"id": str(plan_a.id)},
            )
        ).scalar_one()
        other_visible = (
            await async_session.execute(
                text("SELECT COUNT(*) FROM billing_plans WHERE id = :id"),
                {"id": str(plan_b.id)},
            )
        ).scalar_one()
        assert own_visible == 1
        assert other_visible == 0
    finally:
        if async_session.in_transaction():
            await async_session.rollback()
        await async_session.execute(text("RESET ROLE"))
