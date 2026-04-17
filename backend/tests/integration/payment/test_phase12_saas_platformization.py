from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from financeops.db.models.payment import BillingEntitlement, BillingInvoice, BillingPayment
from financeops.modules.payment.application.entitlement_service import EntitlementService
from financeops.modules.payment.domain.enums import BillingCycle, PlanTier
from financeops.services.audit_writer import AuditWriter
from tests.integration.payment.helpers import create_plan, create_subscription


@pytest.mark.asyncio
@pytest.mark.integration
async def test_phase12_generate_invoice_with_usage_overage(
    async_client: AsyncClient,
    api_session_factory,
    test_user,
    test_access_token: str,
    mock_payment_provider,
) -> None:
    async with api_session_factory() as db:
        plan = await create_plan(
            async_session=db,
            tenant_id=test_user.tenant_id,
            plan_tier=PlanTier.PROFESSIONAL,
            billing_cycle=BillingCycle.MONTHLY,
            price="100.00",
        )
        subscription = await create_subscription(
            async_session=db,
            tenant_id=test_user.tenant_id,
            plan_id=plan.id,
        )
        await AuditWriter.insert_financial_record(
            db,
            model_class=BillingEntitlement,
            tenant_id=test_user.tenant_id,
            record_data={
                "plan_id": str(plan.id),
                "feature_name": "ai_cfo",
                "access_type": "quota",
                "limit_value": "2",
            },
            values={
                "plan_id": plan.id,
                "feature_name": "ai_cfo",
                "access_type": "quota",
                "limit_value": 2,
                "metadata_json": {"price_per_unit": "10"},
                "is_active": True,
            },
        )
        service = EntitlementService(db)
        await service.refresh_tenant_entitlements(
            tenant_id=test_user.tenant_id,
            actor_user_id=test_user.id,
        )
        await service.record_usage_event(
            tenant_id=test_user.tenant_id,
            feature_name="ai_cfo",
            usage_quantity=5,
            reference_type="test",
            reference_id="phase12-overage",
            actor_user_id=test_user.id,
        )
        await db.commit()

    response = await async_client.post(
        "/api/v1/billing/generate-invoice",
        headers={
            "Authorization": f"Bearer {test_access_token}",
            "Idempotency-Key": "idem-phase12-gen-1",
        },
        json={"subscription_id": str(subscription.id), "due_in_days": 5},
    )
    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["status"] == "open"
    assert Decimal(payload["amount"]) == Decimal("130.00")

    async with api_session_factory() as db:
        payment_rows = list(
            (
                await db.execute(
                    select(BillingPayment).where(
                        BillingPayment.tenant_id == test_user.tenant_id,
                    )
                )
            ).scalars()
        )
    assert payment_rows


@pytest.mark.asyncio
@pytest.mark.integration
async def test_phase12_entitlement_refresh_and_usage_endpoints(
    async_client: AsyncClient,
    async_session,
    test_user,
    test_access_token: str,
    mock_payment_provider,
) -> None:
    plan = await create_plan(
        async_session=async_session,
        tenant_id=test_user.tenant_id,
        plan_tier=PlanTier.STARTER,
        billing_cycle=BillingCycle.MONTHLY,
        price="0.00",
    )
    await create_subscription(
        async_session=async_session,
        tenant_id=test_user.tenant_id,
        plan_id=plan.id,
    )
    await AuditWriter.insert_financial_record(
        async_session,
        model_class=BillingEntitlement,
        tenant_id=test_user.tenant_id,
        record_data={
            "plan_id": str(plan.id),
            "feature_name": "analytics",
            "access_type": "boolean",
            "limit_value": "1",
        },
        values={
            "plan_id": plan.id,
            "feature_name": "analytics",
            "access_type": "boolean",
            "limit_value": 1,
            "metadata_json": {},
            "is_active": True,
        },
    )
    await async_session.commit()

    auth = {"Authorization": f"Bearer {test_access_token}"}
    refresh_resp = await async_client.post(
        "/api/v1/billing/entitlements/refresh",
        headers=auth,
        json={},
    )
    assert refresh_resp.status_code == 200
    assert refresh_resp.json()["data"]["inserted"] >= 1

    usage_record = await async_client.post(
        "/api/v1/billing/usage/record",
        headers=auth,
        json={"feature_name": "analytics", "usage_quantity": 3},
    )
    assert usage_record.status_code == 200
    assert usage_record.json()["data"]["allowed"] is True

    usage_summary = await async_client.get("/api/v1/billing/usage", headers=auth)
    assert usage_summary.status_code == 200
    items = usage_summary.json()["data"]["items"]
    analytics_rows = [row for row in items if row["feature_name"] == "analytics"]
    assert analytics_rows
    assert analytics_rows[0]["total_usage"] >= 3


@pytest.mark.asyncio
@pytest.mark.integration
async def test_phase12_entitlement_guard_denies_without_configuration(
    async_client: AsyncClient,
    test_access_token: str,
) -> None:
    response = await async_client.get(
        "/api/v1/analytics/health",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 403
    assert "Entitlement denied" in str(response.json())


@pytest.mark.asyncio
@pytest.mark.integration
async def test_phase12_webhook_updates_invoice_and_payment_status(
    async_client: AsyncClient,
    api_session_factory,
    test_user,
    test_access_token: str,
    mock_payment_provider,
) -> None:
    async with api_session_factory() as db:
        plan = await create_plan(
            async_session=db,
            tenant_id=test_user.tenant_id,
            plan_tier=PlanTier.PROFESSIONAL,
            billing_cycle=BillingCycle.MONTHLY,
            price="50.00",
        )
        await create_subscription(
            async_session=db,
            tenant_id=test_user.tenant_id,
            plan_id=plan.id,
        )
        await db.commit()

    generate_resp = await async_client.post(
        "/api/v1/billing/generate-invoice",
        headers={
            "Authorization": f"Bearer {test_access_token}",
            "Idempotency-Key": "idem-phase12-gen-2",
        },
        json={},
    )
    assert generate_resp.status_code == 200

    async with api_session_factory() as db:
        current_invoice = (
            await db.execute(
                select(BillingInvoice)
                .where(BillingInvoice.tenant_id == test_user.tenant_id)
                .order_by(BillingInvoice.created_at.desc(), BillingInvoice.id.desc())
                .limit(1)
            )
        ).scalar_one()

    webhook_payload = {
        "id": f"evt_{uuid.uuid4().hex[:12]}",
        "type": "invoice.payment_succeeded",
        "data": {
            "object": {
                "id": current_invoice.provider_invoice_id,
                "amount_paid": 5000,
                "metadata": {"tenant_id": str(test_user.tenant_id)},
            }
        },
    }
    webhook_resp = await async_client.post(
        f"/api/v1/billing/webhook?provider=stripe&tenant_id={test_user.tenant_id}",
        headers={"Stripe-Signature": "sig"},
        json=webhook_payload,
    )
    assert webhook_resp.status_code == 200
    assert webhook_resp.json()["data"]["accepted"] is True

    async with api_session_factory() as db:
        latest_invoice = (
            await db.execute(
                select(BillingInvoice)
                .where(
                    BillingInvoice.tenant_id == test_user.tenant_id,
                    BillingInvoice.provider_invoice_id == current_invoice.provider_invoice_id,
                )
                .order_by(BillingInvoice.created_at.desc(), BillingInvoice.id.desc())
                .limit(1)
            )
        ).scalar_one()
    assert latest_invoice.status == "paid"
    assert latest_invoice.paid_at is not None

    async with api_session_factory() as db:
        payment_rows = list(
            (
                await db.execute(
                    select(BillingPayment)
                    .where(BillingPayment.tenant_id == test_user.tenant_id)
                    .order_by(BillingPayment.created_at.desc())
                )
            ).scalars()
        )
    assert any(row.payment_status == "succeeded" for row in payment_rows)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_phase12_webhook_duplicate_event_is_idempotent(
    async_client: AsyncClient,
    api_session_factory,
    test_user,
    test_access_token: str,
    mock_payment_provider,
) -> None:
    async with api_session_factory() as db:
        plan = await create_plan(
            async_session=db,
            tenant_id=test_user.tenant_id,
            plan_tier=PlanTier.PROFESSIONAL,
            billing_cycle=BillingCycle.MONTHLY,
            price="50.00",
        )
        await create_subscription(
            async_session=db,
            tenant_id=test_user.tenant_id,
            plan_id=plan.id,
        )
        await db.commit()

    generate_resp = await async_client.post(
        "/api/v1/billing/generate-invoice",
        headers={
            "Authorization": f"Bearer {test_access_token}",
            "Idempotency-Key": "idem-phase12-gen-dup",
        },
        json={},
    )
    assert generate_resp.status_code == 200

    async with api_session_factory() as db:
        current_invoice = (
            await db.execute(
                select(BillingInvoice)
                .where(BillingInvoice.tenant_id == test_user.tenant_id)
                .order_by(BillingInvoice.created_at.desc(), BillingInvoice.id.desc())
                .limit(1)
            )
        ).scalar_one()

    event_id = f"evt_dup_{uuid.uuid4().hex[:12]}"
    webhook_payload = {
        "id": event_id,
        "type": "invoice.payment_succeeded",
        "data": {
            "object": {
                "id": current_invoice.provider_invoice_id,
                "amount_paid": 5000,
                "metadata": {"tenant_id": str(test_user.tenant_id)},
            }
        },
    }

    first = await async_client.post(
        f"/api/v1/billing/webhook?provider=stripe&tenant_id={test_user.tenant_id}",
        headers={"Stripe-Signature": "sig"},
        json=webhook_payload,
    )
    second = await async_client.post(
        f"/api/v1/billing/webhook?provider=stripe&tenant_id={test_user.tenant_id}",
        headers={"Stripe-Signature": "sig"},
        json=webhook_payload,
    )
    assert first.status_code == 200
    assert second.status_code == 200

    async with api_session_factory() as db:
        latest_invoice = (
            await db.execute(
                select(BillingInvoice)
                .where(
                    BillingInvoice.tenant_id == test_user.tenant_id,
                    BillingInvoice.provider_invoice_id == current_invoice.provider_invoice_id,
                )
                .order_by(BillingInvoice.created_at.desc(), BillingInvoice.id.desc())
                .limit(1)
            )
        ).scalar_one()
    assert latest_invoice.status == "paid"

    async with api_session_factory() as db:
        succeeded_rows = list(
            (
                await db.execute(
                    select(BillingPayment).where(
                        BillingPayment.tenant_id == test_user.tenant_id,
                        BillingPayment.provider_reference == event_id,
                        BillingPayment.payment_status == "succeeded",
                    )
                )
            ).scalars()
        )
    assert len(succeeded_rows) == 1
