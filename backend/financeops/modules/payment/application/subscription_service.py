from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import NotFoundError
from financeops.db.models.payment import GracePeriodLog, SubscriptionEvent, TenantSubscription
from financeops.modules.payment.application.grace_period_service import GracePeriodService
from financeops.modules.payment.domain.enums import OnboardingMode, SubscriptionStatus
from financeops.services.audit_writer import AuditWriter


class SubscriptionService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_subscription_record(
        self,
        *,
        tenant_id: uuid.UUID,
        plan_id: uuid.UUID,
        provider: str,
        provider_subscription_id: str,
        provider_customer_id: str,
        billing_cycle: str,
        period_start: date,
        period_end: date,
        trial_start: date | None,
        trial_end: date | None,
        billing_country: str,
        billing_currency: str,
        onboarding_mode: OnboardingMode,
        metadata: dict[str, Any],
        created_by: uuid.UUID,
    ) -> TenantSubscription:
        status = SubscriptionStatus.TRIALING.value if trial_end else SubscriptionStatus.ACTIVE.value
        row = await AuditWriter.insert_financial_record(
            self._session,
            model_class=TenantSubscription,
            tenant_id=tenant_id,
            record_data={
                "plan_id": str(plan_id),
                "provider": provider,
                "provider_subscription_id": provider_subscription_id,
            },
            values={
                "plan_id": plan_id,
                "provider": provider,
                "provider_subscription_id": provider_subscription_id,
                "provider_customer_id": provider_customer_id,
                "status": status,
                "billing_cycle": billing_cycle,
                "current_period_start": period_start,
                "current_period_end": period_end,
                "trial_start": trial_start,
                "trial_end": trial_end,
                "start_date": period_start,
                "end_date": period_end,
                "trial_end_date": trial_end,
                "auto_renew": True,
                "cancelled_at": None,
                "cancel_at_period_end": False,
                "onboarding_mode": onboarding_mode.value,
                "billing_country": billing_country.upper(),
                "billing_currency": billing_currency.upper(),
                "metadata_json": metadata,
            },
        )
        await self._emit_event(
            tenant_id=tenant_id,
            subscription_id=row.id,
            event_type="CREATED",
            from_status=None,
            to_status=status,
            provider_event_id=None,
        )
        return row

    async def mark_payment_failed(
        self,
        *,
        tenant_id: uuid.UUID,
        subscription_id: uuid.UUID,
        reason: str,
        created_by: uuid.UUID,
    ) -> tuple[TenantSubscription, GracePeriodLog]:
        subscription = await self.get_subscription(tenant_id=tenant_id, subscription_id=subscription_id)
        revised = await self.append_subscription_revision(
            source=subscription,
            status=SubscriptionStatus.PAST_DUE.value,
        )
        start, end, grace_days = GracePeriodService.grace_window()
        log_row = await AuditWriter.insert_financial_record(
            self._session,
            model_class=GracePeriodLog,
            tenant_id=tenant_id,
            record_data={
                "subscription_id": str(subscription.id),
                "grace_period_start": start.isoformat(),
                "grace_period_end": end.isoformat(),
            },
            values={
                "subscription_id": revised.id,
                "grace_period_start": start,
                "grace_period_end": end,
                "grace_period_days": grace_days,
                "reason": reason,
                "resolved_at": None,
                "resolved_by": None,
                "resolution": None,
            },
        )
        await self._emit_event(
            tenant_id=tenant_id,
            subscription_id=revised.id,
            event_type="PAYMENT_FAILED",
            from_status=SubscriptionStatus.ACTIVE.value,
            to_status=SubscriptionStatus.PAST_DUE.value,
            provider_event_id=None,
        )
        await self._emit_event(
            tenant_id=tenant_id,
            subscription_id=revised.id,
            event_type="GRACE_PERIOD_STARTED",
            from_status=SubscriptionStatus.PAST_DUE.value,
            to_status=SubscriptionStatus.GRACE_PERIOD.value,
            provider_event_id=None,
        )
        return revised, log_row

    async def suspend_if_grace_expired(
        self,
        *,
        tenant_id: uuid.UUID,
        subscription_id: uuid.UUID,
    ) -> TenantSubscription:
        subscription = await self.get_subscription(tenant_id=tenant_id, subscription_id=subscription_id)
        revised = await self.append_subscription_revision(
            source=subscription,
            status=SubscriptionStatus.SUSPENDED.value,
        )
        await self._emit_event(
            tenant_id=tenant_id,
            subscription_id=revised.id,
            event_type="SUSPENDED",
            from_status=SubscriptionStatus.GRACE_PERIOD.value,
            to_status=SubscriptionStatus.SUSPENDED.value,
            provider_event_id=None,
        )
        return revised

    async def reactivate(
        self,
        *,
        tenant_id: uuid.UUID,
        subscription_id: uuid.UUID,
        provider_event_id: str | None,
    ) -> TenantSubscription:
        subscription = await self.get_subscription(tenant_id=tenant_id, subscription_id=subscription_id)
        previous = subscription.status
        revised = await self.append_subscription_revision(
            source=subscription,
            status=SubscriptionStatus.ACTIVE.value,
        )
        await self._emit_event(
            tenant_id=tenant_id,
            subscription_id=revised.id,
            event_type="REACTIVATED",
            from_status=previous,
            to_status=SubscriptionStatus.ACTIVE.value,
            provider_event_id=provider_event_id,
        )
        return revised

    async def append_subscription_revision(
        self,
        *,
        source: TenantSubscription,
        plan_id: uuid.UUID | None = None,
        status: str | None = None,
        cancel_at_period_end: bool | None = None,
        cancelled_at: datetime | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TenantSubscription:
        next_plan_id = plan_id or source.plan_id
        next_status = status or source.status
        next_cancel_at_period_end = source.cancel_at_period_end if cancel_at_period_end is None else cancel_at_period_end
        next_cancelled_at = cancelled_at if cancelled_at is not None else source.cancelled_at
        next_metadata = dict(source.metadata_json or {}) if metadata is None else metadata
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=TenantSubscription,
            tenant_id=source.tenant_id,
            record_data={
                "plan_id": str(next_plan_id),
                "provider": source.provider,
                "provider_subscription_id": source.provider_subscription_id,
                "status": next_status,
                "period_end": source.current_period_end.isoformat(),
            },
            values={
                "plan_id": next_plan_id,
                "provider": source.provider,
                "provider_subscription_id": source.provider_subscription_id,
                "provider_customer_id": source.provider_customer_id,
                "status": next_status,
                "billing_cycle": source.billing_cycle,
                "current_period_start": source.current_period_start,
                "current_period_end": source.current_period_end,
                "trial_start": source.trial_start,
                "trial_end": source.trial_end,
                "start_date": source.start_date or source.current_period_start,
                "end_date": source.end_date or source.current_period_end,
                "trial_end_date": source.trial_end_date or source.trial_end,
                "auto_renew": not next_cancel_at_period_end,
                "cancelled_at": next_cancelled_at,
                "cancel_at_period_end": next_cancel_at_period_end,
                "onboarding_mode": source.onboarding_mode,
                "billing_country": source.billing_country,
                "billing_currency": source.billing_currency,
                "metadata_json": next_metadata,
            },
        )

    async def get_active_subscription_for_tenant(self, *, tenant_id: uuid.UUID) -> TenantSubscription | None:
        return (
            await self._session.execute(
                select(TenantSubscription)
                .where(TenantSubscription.tenant_id == tenant_id)
                .order_by(TenantSubscription.created_at.desc(), TenantSubscription.id.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

    async def get_subscription(self, *, tenant_id: uuid.UUID, subscription_id: uuid.UUID) -> TenantSubscription:
        row = (
            await self._session.execute(
                select(TenantSubscription).where(
                    TenantSubscription.tenant_id == tenant_id,
                    TenantSubscription.id == subscription_id,
                )
            )
        ).scalar_one_or_none()
        if row is None:
            raise NotFoundError("Subscription not found")
        return row

    async def _emit_event(
        self,
        *,
        tenant_id: uuid.UUID,
        subscription_id: uuid.UUID,
        event_type: str,
        from_status: str | None,
        to_status: str,
        provider_event_id: str | None,
    ) -> SubscriptionEvent:
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=SubscriptionEvent,
            tenant_id=tenant_id,
            record_data={
                "subscription_id": str(subscription_id),
                "event_type": event_type,
                "to_status": to_status,
                "provider_event_id": provider_event_id or "",
            },
            values={
                "subscription_id": subscription_id,
                "event_type": event_type,
                "from_plan_id": None,
                "to_plan_id": None,
                "from_status": from_status,
                "to_status": to_status,
                "provider_event_id": provider_event_id,
                "metadata_json": {},
            },
        )
