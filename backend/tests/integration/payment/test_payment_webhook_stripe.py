from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

import pytest

from financeops.db.models.payment import BillingInvoice, BillingPayment, WebhookEvent
from financeops.modules.payment.application.invoice_service import InvoiceService
from financeops.modules.payment.domain.enums import BillingCycle, PlanTier
from financeops.main import app
from tests.integration.payment.helpers import create_plan, create_subscription


@pytest.mark.asyncio
@pytest.mark.integration
async def test_stripe_webhook_returns_200_and_accepts_event(
    async_client: AsyncClient,
    test_user,
    mock_payment_provider,
) -> None:
    payload = {
        "id": "evt_stripe_1",
        "type": "invoice.payment_succeeded",
        "data": {"object": {"metadata": {"tenant_id": str(test_user.tenant_id)}}},
    }
    response = await async_client.post(
        "/api/v1/billing/webhooks/stripe",
        headers={"Stripe-Signature": "test-signature"},
        content=json.dumps(payload).encode("utf-8"),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["accepted"] is True


@pytest.mark.asyncio
@pytest.mark.integration
async def test_stripe_webhook_returns_200_on_processing_error(
    async_client: AsyncClient,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _raise(*args, **kwargs):
        raise RuntimeError("handler boom")

    monkeypatch.setattr(
        "financeops.modules.payment.api.webhooks.WebhookService.handle_webhook",
        _raise,
    )
    payload = {
        "id": "evt_stripe_2",
        "type": "invoice.payment_succeeded",
        "data": {"object": {"metadata": {"tenant_id": str(test_user.tenant_id)}}},
    }
    response = await async_client.post(
        "/api/v1/billing/webhooks/stripe",
        headers={"Stripe-Signature": "test-signature"},
        content=json.dumps(payload).encode("utf-8"),
    )
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["accepted"] is True
    assert body["processed"] is False


@pytest.mark.asyncio
@pytest.mark.integration
async def test_stripe_webhook_duplicate_event_is_insert_first_idempotent(
    api_session_factory,
    test_user,
    mock_payment_provider,
) -> None:
    provider_invoice_id = f"inv_{test_user.tenant_id.hex[:8]}"
    async with api_session_factory() as db:
        plan = await create_plan(
            async_session=db,
            tenant_id=test_user.tenant_id,
            plan_tier=PlanTier.PROFESSIONAL,
            billing_cycle=BillingCycle.MONTHLY,
            price="50.00",
        )
        subscription = await create_subscription(
            async_session=db,
            tenant_id=test_user.tenant_id,
            plan_id=plan.id,
        )
        invoice_service = InvoiceService(db)
        await invoice_service.create_invoice_record(
            tenant_id=test_user.tenant_id,
            subscription_id=subscription.id,
            provider_invoice_id=provider_invoice_id,
            currency="USD",
            subtotal=Decimal("50.00"),
            tax=Decimal("0.00"),
            total=Decimal("50.00"),
            due_date=(datetime.now(UTC) + timedelta(days=7)).date(),
            line_items=[{"description": "Webhook invoice", "amount": "50.00", "currency": "USD"}],
        )
        await db.commit()

    event_id = "evt_insert_first_duplicate"
    payload = {
        "id": event_id,
        "type": "invoice.payment_succeeded",
        "data": {
            "object": {
                "id": provider_invoice_id,
                "amount_paid": 5000,
                "metadata": {"tenant_id": str(test_user.tenant_id)},
            }
        },
    }

    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client_one, AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client_two:
        responses = await asyncio.gather(
            client_one.post(
                "/api/v1/billing/webhooks/stripe",
                headers={"Stripe-Signature": "test-signature"},
                content=json.dumps(payload).encode("utf-8"),
            ),
            client_two.post(
                "/api/v1/billing/webhooks/stripe",
                headers={"Stripe-Signature": "test-signature"},
                content=json.dumps(payload).encode("utf-8"),
            ),
        )

    assert all(response.status_code == 200 for response in responses)

    async with api_session_factory() as db:
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
        invoice_rows = list(
            (
                await db.execute(
                    select(BillingInvoice)
                    .where(
                        BillingInvoice.tenant_id == test_user.tenant_id,
                        BillingInvoice.provider_invoice_id == provider_invoice_id,
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
                    )
                )
            ).scalars()
        )

    assert len(webhook_rows) == 1
    assert len(invoice_rows) == 2
    assert invoice_rows[-1].status == "paid"
    assert len(payment_rows) == 1
    assert payment_rows[0].payment_status == "succeeded"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_stripe_webhook_delayed_replay_across_fresh_clients_stays_idempotent(
    api_session_factory,
    test_user,
    mock_payment_provider,
) -> None:
    provider_invoice_id = f"inv_replay_{test_user.tenant_id.hex[:8]}"
    async with api_session_factory() as db:
        plan = await create_plan(
            async_session=db,
            tenant_id=test_user.tenant_id,
            plan_tier=PlanTier.PROFESSIONAL,
            billing_cycle=BillingCycle.MONTHLY,
            price="50.00",
        )
        subscription = await create_subscription(
            async_session=db,
            tenant_id=test_user.tenant_id,
            plan_id=plan.id,
        )
        invoice_service = InvoiceService(db)
        await invoice_service.create_invoice_record(
            tenant_id=test_user.tenant_id,
            subscription_id=subscription.id,
            provider_invoice_id=provider_invoice_id,
            currency="USD",
            subtotal=Decimal("50.00"),
            tax=Decimal("0.00"),
            total=Decimal("50.00"),
            due_date=(datetime.now(UTC) + timedelta(days=7)).date(),
            line_items=[{"description": "Webhook invoice", "amount": "50.00", "currency": "USD"}],
        )
        await db.commit()

    event_id = "evt_delayed_replay"
    payload_bytes = json.dumps(
        {
            "id": event_id,
            "type": "invoice.payment_succeeded",
            "data": {
                "object": {
                    "id": provider_invoice_id,
                    "amount_paid": 5000,
                    "metadata": {"tenant_id": str(test_user.tenant_id)},
                }
            },
        }
    ).encode("utf-8")

    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as first_client:
        first = await first_client.post(
            "/api/v1/billing/webhooks/stripe",
            headers={"Stripe-Signature": "test-signature"},
            content=payload_bytes,
        )

    assert first.status_code == 200

    async with api_session_factory() as db:
        first_payment_rows = list(
            (
                await db.execute(
                    select(BillingPayment).where(
                        BillingPayment.tenant_id == test_user.tenant_id,
                        BillingPayment.provider_reference == event_id,
                    )
                )
            ).scalars()
        )
        assert len(first_payment_rows) == 1

    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as replay_client:
        replay = await replay_client.post(
            "/api/v1/billing/webhooks/stripe",
            headers={"Stripe-Signature": "test-signature"},
            content=payload_bytes,
        )

    assert replay.status_code == 200

    async with api_session_factory() as db:
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
        invoice_rows = list(
            (
                await db.execute(
                    select(BillingInvoice)
                    .where(
                        BillingInvoice.tenant_id == test_user.tenant_id,
                        BillingInvoice.provider_invoice_id == provider_invoice_id,
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
                    )
                )
            ).scalars()
        )

    assert len(webhook_rows) == 1
    assert len(invoice_rows) == 2
    assert invoice_rows[-1].status == "paid"
    assert len(payment_rows) == 1
    assert payment_rows[0].payment_status == "succeeded"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_stripe_webhook_processing_failure_is_logged_and_replay_stays_side_effect_free(
    async_client: AsyncClient,
    api_session_factory,
    test_user,
    mock_payment_provider,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    provider_invoice_id = f"inv_fail_{test_user.tenant_id.hex[:8]}"
    async with api_session_factory() as db:
        plan = await create_plan(
            async_session=db,
            tenant_id=test_user.tenant_id,
            plan_tier=PlanTier.PROFESSIONAL,
            billing_cycle=BillingCycle.MONTHLY,
            price="50.00",
        )
        subscription = await create_subscription(
            async_session=db,
            tenant_id=test_user.tenant_id,
            plan_id=plan.id,
        )
        invoice_service = InvoiceService(db)
        await invoice_service.create_invoice_record(
            tenant_id=test_user.tenant_id,
            subscription_id=subscription.id,
            provider_invoice_id=provider_invoice_id,
            currency="USD",
            subtotal=Decimal("50.00"),
            tax=Decimal("0.00"),
            total=Decimal("50.00"),
            due_date=(datetime.now(UTC) + timedelta(days=7)).date(),
            line_items=[{"description": "Webhook invoice", "amount": "50.00", "currency": "USD"}],
        )
        await db.commit()

    async def _boom(*args, **kwargs):
        raise RuntimeError("handler boom")

    monkeypatch.setattr(
        "financeops.modules.payment.application.webhook_service.WebhookService._route_event",
        _boom,
    )

    event_id = "evt_processing_failure"
    payload = {
        "id": event_id,
        "type": "invoice.payment_succeeded",
        "data": {
            "object": {
                "id": provider_invoice_id,
                "amount_paid": 5000,
                "metadata": {"tenant_id": str(test_user.tenant_id)},
            }
        },
    }

    caplog.set_level(
        logging.INFO,
        logger="financeops.modules.payment.application.webhook_service",
    )

    first = await async_client.post(
        "/api/v1/billing/webhooks/stripe",
        headers={"Stripe-Signature": "test-signature"},
        content=json.dumps(payload).encode("utf-8"),
    )
    second = await async_client.post(
        "/api/v1/billing/webhooks/stripe",
        headers={"Stripe-Signature": "test-signature"},
        content=json.dumps(payload).encode("utf-8"),
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["data"]["accepted"] is True
    assert second.json()["data"]["accepted"] is True

    async with api_session_factory() as db:
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
        invoice_rows = list(
            (
                await db.execute(
                    select(BillingInvoice)
                    .where(
                        BillingInvoice.tenant_id == test_user.tenant_id,
                        BillingInvoice.provider_invoice_id == provider_invoice_id,
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
                    )
                )
            ).scalars()
        )

    assert len(webhook_rows) == 1
    assert len(invoice_rows) == 1
    assert invoice_rows[0].status == "open"
    assert len(payment_rows) == 0
    assert any("payment_webhook_processing_failed" in record.message for record in caplog.records)
    assert any("payment_webhook_duplicate_ignored" in record.message for record in caplog.records)
