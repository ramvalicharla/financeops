from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import NotFoundError, ValidationError
from financeops.db.models.payment import BillingPlan, ProrationRecord, TenantSubscription
from financeops.modules.payment.application.proration_service import ProrationService
from financeops.modules.payment.application.provider_router import resolve_provider
from financeops.modules.payment.application.subscription_service import SubscriptionService
from financeops.modules.payment.application.entitlement_service import EntitlementService
from financeops.modules.payment.application.trial_service import TrialService
from financeops.modules.payment.domain.enums import BillingCycle, OnboardingMode, PaymentProvider
from financeops.modules.payment.infrastructure.providers.registry import get_provider
from financeops.services.audit_writer import AuditWriter


class BillingService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._subscription_service = SubscriptionService(session)
        self._entitlement_service = EntitlementService(session)

    async def create_subscription(
        self,
        *,
        tenant_id: uuid.UUID,
        plan_id: uuid.UUID,
        email: str,
        name: str,
        billing_country: str,
        billing_currency: str,
        billing_cycle: BillingCycle,
        onboarding_mode: OnboardingMode,
        provider_override: PaymentProvider | None,
        metadata: dict[str, Any],
        created_by: uuid.UUID,
    ) -> TenantSubscription:
        plan = (
            await self._session.execute(
                select(BillingPlan).where(BillingPlan.tenant_id == tenant_id, BillingPlan.id == plan_id)
            )
        ).scalar_one_or_none()
        if plan is None:
            raise NotFoundError("Billing plan not found")

        provider = resolve_provider(billing_country=billing_country, override=provider_override)
        provider_impl = get_provider(provider)

        customer_result = await provider_impl.create_customer(
            tenant_id=str(tenant_id),
            email=email,
            name=name,
            metadata=metadata,
        )
        if not customer_result.success or not customer_result.provider_id:
            raise ValidationError(customer_result.error_message or "Failed to create provider customer")

        subscription_result = await provider_impl.create_subscription(
            customer_id=customer_result.provider_id,
            plan_id=str(plan_id),
            billing_cycle=billing_cycle,
            trial_days=int(plan.trial_days),
            metadata=metadata,
        )
        if not subscription_result.success or not subscription_result.provider_id:
            raise ValidationError(subscription_result.error_message or "Failed to create provider subscription")

        trial_start, trial_end = TrialService.resolve_trial_window(trial_days=int(plan.trial_days))
        period_start = datetime.now(UTC).date()
        period_end = date.fromordinal(period_start.toordinal() + (30 if billing_cycle == BillingCycle.MONTHLY else 365))

        row = await self._subscription_service.create_subscription_record(
            tenant_id=tenant_id,
            plan_id=plan_id,
            provider=provider.value,
            provider_subscription_id=subscription_result.provider_id,
            provider_customer_id=customer_result.provider_id,
            billing_cycle=billing_cycle.value,
            period_start=period_start,
            period_end=period_end,
            trial_start=trial_start,
            trial_end=trial_end,
            billing_country=billing_country,
            billing_currency=billing_currency,
            onboarding_mode=onboarding_mode,
            metadata={
                **metadata,
                "annual_discount_pct": str(plan.annual_discount_pct),
            },
            created_by=created_by,
        )
        await self._entitlement_service.refresh_tenant_entitlements(
            tenant_id=tenant_id,
            actor_user_id=created_by,
        )
        return row

    async def upgrade_subscription(
        self,
        *,
        tenant_id: uuid.UUID,
        subscription_id: uuid.UUID,
        to_plan_id: uuid.UUID,
        created_by: uuid.UUID,
        prorate: bool = True,
    ) -> ProrationRecord:
        subscription = await self._subscription_service.get_subscription(
            tenant_id=tenant_id,
            subscription_id=subscription_id,
        )
        from_plan = (
            await self._session.execute(
                select(BillingPlan).where(BillingPlan.tenant_id == tenant_id, BillingPlan.id == subscription.plan_id)
            )
        ).scalar_one()
        to_plan = (
            await self._session.execute(
                select(BillingPlan).where(BillingPlan.tenant_id == tenant_id, BillingPlan.id == to_plan_id)
            )
        ).scalar_one()

        provider_impl = get_provider(PaymentProvider(subscription.provider))
        provider_result = await provider_impl.upgrade_subscription(
            subscription_id=subscription.provider_subscription_id,
            new_plan_id=str(to_plan_id),
            prorate=prorate,
        )
        if not provider_result.success:
            raise ValidationError(provider_result.error_message or "Provider upgrade failed")

        days_remaining = max((subscription.current_period_end - datetime.now(UTC).date()).days, 0)
        total_days = 30 if subscription.billing_cycle == BillingCycle.MONTHLY.value else 365
        from_price = from_plan.base_price_inr if subscription.billing_currency.upper() == "INR" else from_plan.base_price_usd
        to_price = to_plan.base_price_inr if subscription.billing_currency.upper() == "INR" else to_plan.base_price_usd
        proration = ProrationService.calculate(
            from_plan_price=Decimal(str(from_price)),
            to_plan_price=Decimal(str(to_price)),
            days_remaining=days_remaining,
            total_days=total_days,
            currency=subscription.billing_currency,
        )

        await self._subscription_service.append_subscription_revision(
            source=subscription,
            plan_id=to_plan_id,
        )
        await self._entitlement_service.refresh_tenant_entitlements(
            tenant_id=tenant_id,
            actor_user_id=created_by,
        )

        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=ProrationRecord,
            tenant_id=tenant_id,
            record_data={
                "subscription_id": str(subscription_id),
                "from_plan_id": str(from_plan.id),
                "to_plan_id": str(to_plan.id),
                "net_adjustment": str(proration.net_adjustment),
            },
            values={
                "subscription_id": subscription_id,
                "from_plan_id": from_plan.id,
                "to_plan_id": to_plan.id,
                "proration_date": datetime.now(UTC).date(),
                "credit_amount": proration.credit_amount,
                "debit_amount": proration.debit_amount,
                "currency": proration.currency,
                "net_adjustment": proration.net_adjustment,
                "applied_to_invoice_id": None,
            },
        )

    async def cancel_subscription(
        self,
        *,
        tenant_id: uuid.UUID,
        subscription_id: uuid.UUID,
        cancel_at_period_end: bool,
    ) -> TenantSubscription:
        subscription = await self._subscription_service.get_subscription(tenant_id=tenant_id, subscription_id=subscription_id)
        provider_impl = get_provider(PaymentProvider(subscription.provider))
        result = await provider_impl.cancel_subscription(
            subscription_id=subscription.provider_subscription_id,
            cancel_at_period_end=cancel_at_period_end,
        )
        if not result.success:
            raise ValidationError(result.error_message or "Provider cancellation failed")
        cancelled_at = datetime.now(UTC) if not cancel_at_period_end else subscription.cancelled_at
        status = "cancelled" if not cancel_at_period_end else subscription.status
        return await self._subscription_service.append_subscription_revision(
            source=subscription,
            status=status,
            cancel_at_period_end=cancel_at_period_end,
            cancelled_at=cancelled_at,
        )

    async def reactivate_subscription(
        self,
        *,
        tenant_id: uuid.UUID,
        subscription_id: uuid.UUID,
    ) -> TenantSubscription:
        subscription = await self._subscription_service.get_subscription(tenant_id=tenant_id, subscription_id=subscription_id)
        provider_impl = get_provider(PaymentProvider(subscription.provider))
        result = await provider_impl.reactivate_subscription(subscription.provider_subscription_id)
        if not result.success:
            raise ValidationError(result.error_message or "Provider reactivation failed")
        row = await self._subscription_service.reactivate(
            tenant_id=tenant_id,
            subscription_id=subscription_id,
            provider_event_id=result.provider_id,
        )
        await self._entitlement_service.refresh_tenant_entitlements(
            tenant_id=tenant_id,
            actor_user_id=None,
        )
        return row
