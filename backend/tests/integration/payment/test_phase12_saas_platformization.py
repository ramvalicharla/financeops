from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from financeops.db.models.payment import BillingEntitlement, BillingInvoice, BillingPayment, WebhookEvent
from financeops.modules.payment.application.entitlement_service import EntitlementService
from financeops.modules.payment.application.invoice_service import InvoiceService
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
        webhook_rows = list(
            (
                await db.execute(
                    select(WebhookEvent).where(
                        WebhookEvent.tenant_id == test_user.tenant_id,
                        WebhookEvent.provider == "stripe",
                        WebhookEvent.provider_event_id == event_id,
                    )
                )
            ).scalars()
        )
    assert len(succeeded_rows) == 1
    assert len(webhook_rows) == 1


@pytest.mark.asyncio
@pytest.mark.integration
async def test_phase12_generic_webhook_without_event_id_is_idempotent_via_derived_hash(
    async_client: AsyncClient,
    api_session_factory,
    test_user,
    test_access_token: str,
    mock_payment_provider,
) -> None:
    async def _parse_without_event_id(payload: dict) -> tuple[str, dict]:
        provider_event_type = str(payload.get("type") or payload.get("event") or "invoice.paid")
        canonical_map = {
            "invoice.payment_succeeded": "invoice.paid",
            "invoice.paid": "invoice.paid",
            "invoice.payment_failed": "invoice.payment_failed",
            "payment_intent.succeeded": "payment.succeeded",
            "payment.failed": "payment.failed",
            "customer.subscription.updated": "subscription.updated",
            "customer.subscription.deleted": "subscription.cancelled",
        }
        canonical = canonical_map.get(provider_event_type, "invoice.paid")
        return canonical, {
            "provider_event_id": payload.get("id"),
            "provider_event_type": provider_event_type,
            "object": payload.get("data", {}).get("object", {}),
        }

    mock_payment_provider.parse_webhook_event = _parse_without_event_id

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
            "Idempotency-Key": "idem-phase12-gen-derived",
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
        "type": "invoice.payment_succeeded",
        "data": {
            "object": {
                "id": current_invoice.provider_invoice_id,
                "amount_paid": 5000,
                "metadata": {"tenant_id": str(test_user.tenant_id)},
            }
        },
    }
    payload_bytes = __import__("json").dumps(webhook_payload).encode("utf-8")
    derived_event_id = f"derived:stripe:invoice.paid:{hashlib.sha256(payload_bytes).hexdigest()}"

    first = await async_client.post(
        f"/api/v1/billing/webhook?provider=stripe&tenant_id={test_user.tenant_id}",
        headers={"Stripe-Signature": "sig"},
        content=payload_bytes,
    )
    second = await async_client.post(
        f"/api/v1/billing/webhook?provider=stripe&tenant_id={test_user.tenant_id}",
        headers={"Stripe-Signature": "sig"},
        content=payload_bytes,
    )
    assert first.status_code == 200
    assert second.status_code == 200

    async with api_session_factory() as db:
        payment_rows = list(
            (
                await db.execute(
                    select(BillingPayment).where(
                        BillingPayment.tenant_id == test_user.tenant_id,
                        BillingPayment.provider_reference == derived_event_id,
                        BillingPayment.payment_status == "succeeded",
                    )
                )
            ).scalars()
        )
        webhook_rows = list(
            (
                await db.execute(
                    select(WebhookEvent).where(
                        WebhookEvent.tenant_id == test_user.tenant_id,
                        WebhookEvent.provider == "stripe",
                        WebhookEvent.provider_event_id == derived_event_id,
                    )
                )
            ).scalars()
        )
    assert len(payment_rows) == 1
    assert len(webhook_rows) == 1


@pytest.mark.asyncio
@pytest.mark.integration
async def test_phase12_generic_webhook_same_payload_does_not_collide_across_tenants(
    async_client: AsyncClient,
    api_session_factory,
    test_user,
    api_test_tenant,
    mock_payment_provider,
) -> None:
    shared_provider_invoice_id = "inv_cross_tenant_shared"
    event_id = "evt_cross_tenant_shared"

    async with api_session_factory() as db:
        plan_one = await create_plan(
            async_session=db,
            tenant_id=test_user.tenant_id,
            plan_tier=PlanTier.PROFESSIONAL,
            billing_cycle=BillingCycle.MONTHLY,
            price="50.00",
        )
        subscription_one = await create_subscription(
            async_session=db,
            tenant_id=test_user.tenant_id,
            plan_id=plan_one.id,
        )

        plan_two = await create_plan(
            async_session=db,
            tenant_id=api_test_tenant.id,
            plan_tier=PlanTier.PROFESSIONAL,
            billing_cycle=BillingCycle.MONTHLY,
            price="50.00",
        )
        subscription_two = await create_subscription(
            async_session=db,
            tenant_id=api_test_tenant.id,
            plan_id=plan_two.id,
        )

        invoice_service = InvoiceService(db)
        await invoice_service.create_invoice_record(
            tenant_id=test_user.tenant_id,
            subscription_id=subscription_one.id,
            provider_invoice_id=shared_provider_invoice_id,
            currency="USD",
            subtotal=Decimal("50.00"),
            tax=Decimal("0.00"),
            total=Decimal("50.00"),
            due_date=datetime.now(UTC).date(),
            line_items=[{"description": "Tenant one invoice", "amount": "50.00", "currency": "USD"}],
        )
        await invoice_service.create_invoice_record(
            tenant_id=api_test_tenant.id,
            subscription_id=subscription_two.id,
            provider_invoice_id=shared_provider_invoice_id,
            currency="USD",
            subtotal=Decimal("50.00"),
            tax=Decimal("0.00"),
            total=Decimal("50.00"),
            due_date=datetime.now(UTC).date(),
            line_items=[{"description": "Tenant two invoice", "amount": "50.00", "currency": "USD"}],
        )
        await db.commit()

    payload = {
        "id": event_id,
        "type": "invoice.payment_succeeded",
        "data": {
            "object": {
                "id": shared_provider_invoice_id,
                "amount_paid": 5000,
            }
        },
    }

    first = await async_client.post(
        f"/api/v1/billing/webhook?provider=stripe&tenant_id={test_user.tenant_id}",
        headers={"Stripe-Signature": "sig"},
        json=payload,
    )
    second = await async_client.post(
        f"/api/v1/billing/webhook?provider=stripe&tenant_id={api_test_tenant.id}",
        headers={"Stripe-Signature": "sig"},
        json=payload,
    )
    assert first.status_code == 200
    assert second.status_code == 200

    async with api_session_factory() as db:
        tenant_one_webhooks = list(
            (
                await db.execute(
                    select(WebhookEvent).where(
                        WebhookEvent.tenant_id == test_user.tenant_id,
                        WebhookEvent.provider == "stripe",
                        WebhookEvent.provider_event_id == event_id,
                    )
                )
            ).scalars()
        )
        tenant_two_webhooks = list(
            (
                await db.execute(
                    select(WebhookEvent).where(
                        WebhookEvent.tenant_id == api_test_tenant.id,
                        WebhookEvent.provider == "stripe",
                        WebhookEvent.provider_event_id == event_id,
                    )
                )
            ).scalars()
        )
        tenant_one_payments = list(
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
        tenant_two_payments = list(
            (
                await db.execute(
                    select(BillingPayment).where(
                        BillingPayment.tenant_id == api_test_tenant.id,
                        BillingPayment.provider_reference == event_id,
                        BillingPayment.payment_status == "succeeded",
                    )
                )
            ).scalars()
        )
    assert len(tenant_one_webhooks) == 1
    assert len(tenant_two_webhooks) == 1
    assert len(tenant_one_payments) == 1
    assert len(tenant_two_payments) == 1


@pytest.mark.asyncio
@pytest.mark.integration
async def test_phase12_generic_webhook_delayed_replay_does_not_create_extra_side_effects(
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
            "Idempotency-Key": "idem-phase12-gen-delayed-replay",
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

    event_id = f"evt_delayed_generic_{uuid.uuid4().hex[:12]}"
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
    assert first.status_code == 200

    async with api_session_factory() as db:
        first_payment_rows = list(
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
    assert len(first_payment_rows) == 1

    second = await async_client.post(
        f"/api/v1/billing/webhook?provider=stripe&tenant_id={test_user.tenant_id}",
        headers={"Stripe-Signature": "sig"},
        json=webhook_payload,
    )
    assert second.status_code == 200

    async with api_session_factory() as db:
        latest_invoice_rows = list(
            (
                await db.execute(
                    select(BillingInvoice)
                    .where(
                        BillingInvoice.tenant_id == test_user.tenant_id,
                        BillingInvoice.provider_invoice_id == current_invoice.provider_invoice_id,
                    )
                    .order_by(BillingInvoice.created_at.asc(), BillingInvoice.id.asc())
                )
            ).scalars()
        )
        payment_rows = list(
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
        webhook_rows = list(
            (
                await db.execute(
                    select(WebhookEvent).where(
                        WebhookEvent.tenant_id == test_user.tenant_id,
                        WebhookEvent.provider == "stripe",
                        WebhookEvent.provider_event_id == event_id,
                    )
                )
            ).scalars()
        )

    assert len(latest_invoice_rows) == 2
    assert latest_invoice_rows[-1].status == "paid"
    assert len(payment_rows) == 1
    assert len(webhook_rows) == 1
