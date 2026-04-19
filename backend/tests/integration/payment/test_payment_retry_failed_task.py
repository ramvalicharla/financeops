from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

pytestmark = pytest.mark.committed_session

from sqlalchemy import select

from financeops.db.models.payment import BillingInvoice, PaymentMethod, SubscriptionEvent, TenantSubscription
from financeops.modules.payment.application.invoice_service import InvoiceService
from financeops.modules.payment.domain.enums import BillingCycle, InvoiceStatus, PaymentProvider, PlanTier, SubscriptionStatus
from financeops.modules.payment.domain.schemas import PaymentProviderResult
from financeops.services.audit_writer import AuditWriter
from financeops.tasks import payment_tasks
from tests.integration.payment.helpers import create_plan, create_subscription


class _FakeRetryProvider:
    def __init__(self, outcomes: dict[str, PaymentProviderResult | Exception]) -> None:
        self._outcomes = outcomes
        self.calls: list[tuple[str, str]] = []

    async def pay_invoice(self, invoice_id: str, payment_method_id: str) -> PaymentProviderResult:
        self.calls.append((invoice_id, payment_method_id))
        outcome = self._outcomes[invoice_id]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


async def _insert_default_payment_method(
    *,
    async_session,
    tenant_id,
    provider: PaymentProvider,
) -> PaymentMethod:
    return await AuditWriter.insert_financial_record(
        async_session,
        model_class=PaymentMethod,
        tenant_id=tenant_id,
        record_data={
            "provider": provider.value,
            "provider_payment_method_id": f"pm_{provider.value}",
            "is_default": "true",
        },
        values={
            "provider": provider.value,
            "provider_payment_method_id": f"pm_{provider.value}",
            "type": "card",
            "last4": "4242",
            "brand": "visa",
            "expiry_month": 12,
            "expiry_year": 2030,
            "is_default": True,
            "billing_details": {},
        },
    )


async def _create_open_invoice(
    *,
    async_session,
    tenant_id,
    subscription_id,
    provider_invoice_id: str,
) -> BillingInvoice:
    service = InvoiceService(async_session)
    return await service.create_invoice_record(
        tenant_id=tenant_id,
        subscription_id=subscription_id,
        provider_invoice_id=provider_invoice_id,
        currency="USD",
        subtotal=Decimal("50.00"),
        tax=Decimal("0"),
        total=Decimal("50.00"),
        due_date=(datetime.now(UTC) + timedelta(days=7)).date(),
        line_items=[{"description": "Subscription retry", "amount": "50.00", "currency": "USD"}],
    )


async def _latest_subscription(async_session, source: TenantSubscription) -> TenantSubscription:
    return (
        await async_session.execute(
            select(TenantSubscription)
            .where(
                TenantSubscription.tenant_id == source.tenant_id,
                TenantSubscription.provider_subscription_id == source.provider_subscription_id,
            )
            .order_by(TenantSubscription.created_at.desc(), TenantSubscription.id.desc())
            .limit(1)
        )
    ).scalar_one()


async def _latest_invoice(async_session, tenant_id, provider_invoice_id: str) -> BillingInvoice:
    return (
        await async_session.execute(
            select(BillingInvoice)
            .where(
                BillingInvoice.tenant_id == tenant_id,
                BillingInvoice.provider_invoice_id == provider_invoice_id,
            )
            .order_by(BillingInvoice.created_at.desc(), BillingInvoice.id.desc())
            .limit(1)
        )
    ).scalar_one()


async def _append_past_due_retry_revision(
    *,
    async_session,
    source: TenantSubscription,
    retry_count: int,
) -> TenantSubscription:
    next_created_at = (source.created_at or datetime.now(UTC)) + timedelta(microseconds=1)
    return await AuditWriter.insert_financial_record(
        async_session,
        model_class=TenantSubscription,
        tenant_id=source.tenant_id,
        record_data={
            "plan_id": str(source.plan_id),
            "provider": source.provider,
            "provider_subscription_id": source.provider_subscription_id,
            "status": SubscriptionStatus.PAST_DUE.value,
        },
        values={
            "plan_id": source.plan_id,
            "provider": source.provider,
            "provider_subscription_id": source.provider_subscription_id,
            "provider_customer_id": source.provider_customer_id,
            "status": SubscriptionStatus.PAST_DUE.value,
            "billing_cycle": source.billing_cycle,
            "current_period_start": source.current_period_start,
            "current_period_end": source.current_period_end,
            "trial_start": source.trial_start,
            "trial_end": source.trial_end,
            "start_date": source.start_date or source.current_period_start,
            "end_date": source.end_date or source.current_period_end,
            "trial_end_date": source.trial_end_date or source.trial_end,
            "auto_renew": source.auto_renew,
            "cancelled_at": source.cancelled_at,
            "cancel_at_period_end": source.cancel_at_period_end,
            "onboarding_mode": source.onboarding_mode,
            "billing_country": source.billing_country,
            "billing_currency": source.billing_currency,
            "metadata_json": {"payment_retry_count": retry_count},
            "created_at": next_created_at,
        },
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_retry_failed_payments_reactivates_on_success(
    api_session_factory,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
            provider=PaymentProvider.STRIPE,
            status=SubscriptionStatus.PAST_DUE,
        )
        await _insert_default_payment_method(
            async_session=db,
            tenant_id=test_user.tenant_id,
            provider=PaymentProvider.STRIPE,
        )
        invoice = await _create_open_invoice(
            async_session=db,
            tenant_id=test_user.tenant_id,
            subscription_id=subscription.id,
            provider_invoice_id="inv_retry_success",
        )
        await db.commit()
    fake_provider = _FakeRetryProvider(
        {
            invoice.provider_invoice_id: PaymentProviderResult(
                success=True,
                provider_id="pay_123",
                raw_response={"id": "pay_123"},
            )
        }
    )
    monkeypatch.setattr(payment_tasks, "get_provider", lambda _provider: fake_provider)

    async with api_session_factory() as db:
        result = await payment_tasks._retry_failed_payments_async(db)
        await db.commit()

    async with api_session_factory() as read_db:
        latest_subscription = await _latest_subscription(read_db, subscription)
        latest_invoice = await _latest_invoice(read_db, test_user.tenant_id, invoice.provider_invoice_id)

    assert result["reactivated"] == 1
    assert result["failed"] == 0
    assert latest_subscription.status == SubscriptionStatus.ACTIVE.value
    assert latest_subscription.metadata_json["payment_retry_count"] == 0
    assert latest_invoice.status == InvoiceStatus.PAID.value
    assert latest_invoice.paid_at is not None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_retry_failed_payments_keeps_subscription_past_due_on_failure(
    api_session_factory,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
            provider=PaymentProvider.STRIPE,
            status=SubscriptionStatus.PAST_DUE,
        )
        await _insert_default_payment_method(
            async_session=db,
            tenant_id=test_user.tenant_id,
            provider=PaymentProvider.STRIPE,
        )
        invoice = await _create_open_invoice(
            async_session=db,
            tenant_id=test_user.tenant_id,
            subscription_id=subscription.id,
            provider_invoice_id="inv_retry_fail",
        )
        await db.commit()
    fake_provider = _FakeRetryProvider(
        {
            invoice.provider_invoice_id: PaymentProviderResult(
                success=False,
                provider_id=None,
                raw_response={"error": "declined"},
                error_code="card_declined",
                error_message="card_declined",
            )
        }
    )
    monkeypatch.setattr(payment_tasks, "get_provider", lambda _provider: fake_provider)

    async with api_session_factory() as db:
        result = await payment_tasks._retry_failed_payments_async(db)
        await db.commit()

    async with api_session_factory() as read_db:
        latest_subscription = await _latest_subscription(read_db, subscription)
        latest_invoice = await _latest_invoice(read_db, test_user.tenant_id, invoice.provider_invoice_id)

    assert result["reactivated"] == 0
    assert result["failed"] == 1
    assert latest_subscription.status == SubscriptionStatus.PAST_DUE.value
    assert latest_subscription.metadata_json["payment_retry_count"] == 1
    assert latest_subscription.metadata_json["payment_retry_last_error"] == "card_declined"
    assert latest_invoice.status == InvoiceStatus.OPEN.value


@pytest.mark.asyncio
@pytest.mark.integration
async def test_retry_failed_payments_cancels_after_third_failure(
    api_session_factory,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with api_session_factory() as db:
        plan = await create_plan(
            async_session=db,
            tenant_id=test_user.tenant_id,
            plan_tier=PlanTier.PROFESSIONAL,
            billing_cycle=BillingCycle.MONTHLY,
            price="50.00",
        )
        original = await create_subscription(
            async_session=db,
            tenant_id=test_user.tenant_id,
            plan_id=plan.id,
            provider=PaymentProvider.STRIPE,
            status=SubscriptionStatus.PAST_DUE,
        )
        subscription = await _append_past_due_retry_revision(
            async_session=db,
            source=original,
            retry_count=2,
        )
        await _insert_default_payment_method(
            async_session=db,
            tenant_id=test_user.tenant_id,
            provider=PaymentProvider.STRIPE,
        )
        invoice = await _create_open_invoice(
            async_session=db,
            tenant_id=test_user.tenant_id,
            subscription_id=subscription.id,
            provider_invoice_id="inv_retry_cancel",
        )
        await db.commit()
    fake_provider = _FakeRetryProvider(
        {
            invoice.provider_invoice_id: PaymentProviderResult(
                success=False,
                provider_id=None,
                raw_response={"error": "declined"},
                error_code="card_declined",
                error_message="card_declined",
            )
        }
    )
    monkeypatch.setattr(payment_tasks, "get_provider", lambda _provider: fake_provider)

    async with api_session_factory() as db:
        result = await payment_tasks._retry_failed_payments_async(db)
        await db.commit()

    async with api_session_factory() as read_db:
        latest_subscription = await _latest_subscription(read_db, subscription)
        events = list(
            (
                await read_db.execute(
                    select(SubscriptionEvent)
                    .where(
                        SubscriptionEvent.tenant_id == test_user.tenant_id,
                        SubscriptionEvent.subscription_id == latest_subscription.id,
                    )
                )
            ).scalars()
        )

    assert result["cancelled"] == 1
    assert latest_subscription.status == SubscriptionStatus.CANCELLED.value
    assert latest_subscription.cancelled_at is not None
    assert latest_subscription.auto_renew is False
    assert latest_subscription.metadata_json["payment_retry_count"] == 3
    assert any(event.event_type == "CANCELLED" for event in events)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_retry_failed_payments_continues_after_provider_exception(
    api_session_factory,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with api_session_factory() as db:
        plan = await create_plan(
            async_session=db,
            tenant_id=test_user.tenant_id,
            plan_tier=PlanTier.PROFESSIONAL,
            billing_cycle=BillingCycle.MONTHLY,
            price="50.00",
        )
        failing_subscription = await create_subscription(
            async_session=db,
            tenant_id=test_user.tenant_id,
            plan_id=plan.id,
            provider=PaymentProvider.STRIPE,
            status=SubscriptionStatus.PAST_DUE,
        )
        succeeding_subscription = await create_subscription(
            async_session=db,
            tenant_id=test_user.tenant_id,
            plan_id=plan.id,
            provider=PaymentProvider.STRIPE,
            status=SubscriptionStatus.PAST_DUE,
        )
        await _insert_default_payment_method(
            async_session=db,
            tenant_id=test_user.tenant_id,
            provider=PaymentProvider.STRIPE,
        )
        failing_invoice = await _create_open_invoice(
            async_session=db,
            tenant_id=test_user.tenant_id,
            subscription_id=failing_subscription.id,
            provider_invoice_id="inv_retry_exception",
        )
        succeeding_invoice = await _create_open_invoice(
            async_session=db,
            tenant_id=test_user.tenant_id,
            subscription_id=succeeding_subscription.id,
            provider_invoice_id="inv_retry_success_after_exception",
        )
        await db.commit()
    fake_provider = _FakeRetryProvider(
        {
            failing_invoice.provider_invoice_id: RuntimeError("gateway down"),
            succeeding_invoice.provider_invoice_id: PaymentProviderResult(
                success=True,
                provider_id="pay_456",
                raw_response={"id": "pay_456"},
            ),
        }
    )
    monkeypatch.setattr(payment_tasks, "get_provider", lambda _provider: fake_provider)

    async with api_session_factory() as db:
        result = await payment_tasks._retry_failed_payments_async(db)
        await db.commit()

    async with api_session_factory() as read_db:
        latest_failing = await _latest_subscription(read_db, failing_subscription)
        latest_succeeding = await _latest_subscription(read_db, succeeding_subscription)

    assert result["failed"] == 1
    assert result["reactivated"] == 1
    assert latest_failing.status == SubscriptionStatus.PAST_DUE.value
    assert latest_failing.metadata_json["payment_retry_count"] == 1
    assert latest_succeeding.status == SubscriptionStatus.ACTIVE.value
