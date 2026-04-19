from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import select

import pytest

from financeops.db.models.payment import BillingInvoice, BillingPayment, WebhookEvent
from financeops.modules.payment.application.invoice_service import InvoiceService
from financeops.modules.payment.domain.enums import BillingCycle, PlanTier
from tests.integration.payment.helpers import create_plan, create_subscription


@pytest.mark.asyncio
@pytest.mark.integration
async def test_razorpay_webhook_returns_200_and_accepts_event(
    async_client: AsyncClient,
    test_user,
    mock_payment_provider,
) -> None:
    payload = {
        "id": "evt_rzp_1",
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_123",
                    "notes": {"tenant_id": str(test_user.tenant_id)},
                }
            }
        },
    }
    response = await async_client.post(
        "/api/v1/billing/webhooks/razorpay",
        headers={"X-Razorpay-Signature": "test-signature"},
        content=json.dumps(payload).encode("utf-8"),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["accepted"] is True


@pytest.mark.asyncio
@pytest.mark.integration
async def test_razorpay_webhook_duplicate_event_is_idempotent(
    async_client: AsyncClient,
    api_session_factory,
    test_user,
    mock_payment_provider,
) -> None:
    provider_invoice_id = f"rzp_inv_{test_user.tenant_id.hex[:8]}"
    event_id = "evt_rzp_duplicate"

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
            line_items=[{"description": "Razorpay invoice", "amount": "50.00", "currency": "USD"}],
        )
        await db.commit()

    payload_bytes = json.dumps(
        {
            "id": event_id,
            "event": "payment.captured",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_duplicate",
                        "invoice_id": provider_invoice_id,
                        "amount": 5000,
                        "notes": {"tenant_id": str(test_user.tenant_id)},
                    }
                }
            },
        }
    ).encode("utf-8")

    first = await async_client.post(
        "/api/v1/billing/webhooks/razorpay",
        headers={"X-Razorpay-Signature": "test-signature"},
        content=payload_bytes,
    )
    second = await async_client.post(
        "/api/v1/billing/webhooks/razorpay",
        headers={"X-Razorpay-Signature": "test-signature"},
        content=payload_bytes,
    )

    assert first.status_code == 200
    assert second.status_code == 200

    async with api_session_factory() as db:
        webhook_rows = list(
            (
                await db.execute(
                    select(WebhookEvent).where(
                        WebhookEvent.tenant_id == test_user.tenant_id,
                        WebhookEvent.provider == "razorpay",
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
