from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, date, datetime

from sqlalchemy import and_, func, select

from financeops.db.models.payment import CreditLedger, GracePeriodLog, PaymentMethod, SubscriptionEvent, TenantSubscription
from financeops.db.session import AsyncSessionLocal
from financeops.modules.payment.domain.enums import CreditTransactionType, SubscriptionStatus
from financeops.services.audit_writer import AuditWriter
from financeops.tasks.base_task import FinanceOpsTask
from financeops.tasks.celery_app import celery_app


async def _emit_subscription_event(
    *,
    session,
    tenant_id: uuid.UUID,
    subscription_id: uuid.UUID,
    event_type: str,
    from_status: str | None,
    to_status: str,
) -> None:
    await AuditWriter.insert_financial_record(
        session,
        model_class=SubscriptionEvent,
        tenant_id=tenant_id,
        record_data={
            "subscription_id": str(subscription_id),
            "event_type": event_type,
            "to_status": to_status,
        },
        values={
            "subscription_id": subscription_id,
            "event_type": event_type,
            "from_plan_id": None,
            "to_plan_id": None,
            "from_status": from_status,
            "to_status": to_status,
            "provider_event_id": None,
            "metadata_json": {},
        },
    )


async def _append_subscription_revision(
    *,
    session,
    source: TenantSubscription,
    status: str,
) -> TenantSubscription:
    return await AuditWriter.insert_financial_record(
        session,
        model_class=TenantSubscription,
        tenant_id=source.tenant_id,
        record_data={
            "plan_id": str(source.plan_id),
            "provider": source.provider,
            "provider_subscription_id": source.provider_subscription_id,
            "status": status,
        },
        values={
            "plan_id": source.plan_id,
            "provider": source.provider,
            "provider_subscription_id": source.provider_subscription_id,
            "provider_customer_id": source.provider_customer_id,
            "status": status,
            "billing_cycle": source.billing_cycle,
            "current_period_start": source.current_period_start,
            "current_period_end": source.current_period_end,
            "trial_start": source.trial_start,
            "trial_end": source.trial_end,
            "cancelled_at": source.cancelled_at,
            "cancel_at_period_end": source.cancel_at_period_end,
            "onboarding_mode": source.onboarding_mode,
            "billing_country": source.billing_country,
            "billing_currency": source.billing_currency,
            "metadata_json": dict(source.metadata_json or {}),
        },
    )


@celery_app.task(name="payment.check_trial_conversions", base=FinanceOpsTask)
def check_trial_conversions() -> dict[str, int]:
    async def _run() -> dict[str, int]:
        converted = 0
        incomplete = 0
        today = date.today()
        async with AsyncSessionLocal() as session:
            rows = list(
                (
                    await session.execute(
                        select(TenantSubscription).where(
                            TenantSubscription.status == SubscriptionStatus.TRIALING.value,
                            TenantSubscription.trial_end.is_not(None),
                            TenantSubscription.trial_end <= today,
                        )
                    )
                ).scalars()
            )
            for sub in rows:
                has_payment_method = (
                    await session.execute(
                        select(PaymentMethod.id)
                        .where(
                            PaymentMethod.tenant_id == sub.tenant_id,
                            PaymentMethod.is_default.is_(True),
                        )
                        .limit(1)
                    )
                ).scalar_one_or_none() is not None
                old_status = sub.status
                if has_payment_method:
                    revised = await _append_subscription_revision(
                        session=session,
                        source=sub,
                        status=SubscriptionStatus.ACTIVE.value,
                    )
                    converted += 1
                    event = "TRIAL_CONVERTED"
                else:
                    revised = await _append_subscription_revision(
                        session=session,
                        source=sub,
                        status=SubscriptionStatus.INCOMPLETE.value,
                    )
                    incomplete += 1
                    event = "TRIAL_STARTED"
                await _emit_subscription_event(
                    session=session,
                    tenant_id=sub.tenant_id,
                    subscription_id=revised.id,
                    event_type=event,
                    from_status=old_status,
                    to_status=revised.status,
                )
            await session.commit()
        return {"converted": converted, "incomplete": incomplete}

    return asyncio.run(_run())


@celery_app.task(name="payment.check_grace_periods", base=FinanceOpsTask)
def check_grace_periods() -> dict[str, int]:
    async def _run() -> dict[str, int]:
        suspended = 0
        now_ts = datetime.now(UTC)
        async with AsyncSessionLocal() as session:
            rows = list(
                (
                    await session.execute(
                        select(GracePeriodLog)
                        .where(
                            GracePeriodLog.resolved_at.is_(None),
                            GracePeriodLog.grace_period_end <= now_ts,
                        )
                        .order_by(GracePeriodLog.grace_period_end.asc())
                    )
                ).scalars()
            )
            for log_row in rows:
                sub = (
                    await session.execute(
                        select(TenantSubscription).where(
                            TenantSubscription.id == log_row.subscription_id,
                            TenantSubscription.tenant_id == log_row.tenant_id,
                        )
                    )
                ).scalar_one_or_none()
                if sub is None:
                    continue
                revised = await _append_subscription_revision(
                    session=session,
                    source=sub,
                    status=SubscriptionStatus.SUSPENDED.value,
                )
                await AuditWriter.insert_financial_record(
                    session,
                    model_class=GracePeriodLog,
                    tenant_id=log_row.tenant_id,
                    record_data={
                        "subscription_id": str(revised.id),
                        "grace_period_end": log_row.grace_period_end.isoformat(),
                        "resolution": "suspended",
                    },
                    values={
                        "subscription_id": revised.id,
                        "grace_period_start": log_row.grace_period_start,
                        "grace_period_end": log_row.grace_period_end,
                        "grace_period_days": log_row.grace_period_days,
                        "reason": log_row.reason,
                        "resolved_at": now_ts,
                        "resolved_by": "system",
                        "resolution": "suspended",
                    },
                )
                await _emit_subscription_event(
                    session=session,
                    tenant_id=revised.tenant_id,
                    subscription_id=revised.id,
                    event_type="SUSPENDED",
                    from_status=sub.status,
                    to_status=revised.status,
                )
                suspended += 1
            await session.commit()
        return {"suspended": suspended}

    return asyncio.run(_run())


@celery_app.task(name="payment.retry_failed_payments", base=FinanceOpsTask)
def retry_failed_payments() -> dict[str, int]:
    async def _run() -> dict[str, int]:
        reactivated = 0
        async with AsyncSessionLocal() as session:
            rows = list(
                (
                    await session.execute(
                        select(TenantSubscription).where(
                            TenantSubscription.status == SubscriptionStatus.PAST_DUE.value
                        )
                    )
                ).scalars()
            )
            for sub in rows:
                revised = await _append_subscription_revision(
                    session=session,
                    source=sub,
                    status=SubscriptionStatus.ACTIVE.value,
                )
                await _emit_subscription_event(
                    session=session,
                    tenant_id=revised.tenant_id,
                    subscription_id=revised.id,
                    event_type="REACTIVATED",
                    from_status=sub.status,
                    to_status=revised.status,
                )
                reactivated += 1
            await session.commit()
        return {"reactivated": reactivated}

    return asyncio.run(_run())


@celery_app.task(name="payment.expire_credits", base=FinanceOpsTask)
def expire_credits() -> dict[str, int]:
    async def _run() -> dict[str, int]:
        expired_entries = 0
        now_ts = datetime.now(UTC)
        day_key = now_ts.date().isoformat()
        async with AsyncSessionLocal() as session:
            tenant_ids = list(
                (
                    await session.execute(
                        select(CreditLedger.tenant_id)
                        .where(CreditLedger.expires_at.is_not(None), CreditLedger.expires_at <= now_ts)
                        .group_by(CreditLedger.tenant_id)
                    )
                ).scalars()
            )
            for tenant_id in tenant_ids:
                already_posted = (
                    await session.execute(
                        select(CreditLedger.id)
                        .where(
                            CreditLedger.tenant_id == tenant_id,
                            CreditLedger.transaction_type == CreditTransactionType.EXPIRY.value,
                            CreditLedger.reference_id == day_key,
                        )
                        .limit(1)
                    )
                ).scalar_one_or_none()
                if already_posted is not None:
                    continue

                expiring_sum = await session.scalar(
                    select(func.coalesce(func.sum(CreditLedger.credits_delta), 0)).where(
                        CreditLedger.tenant_id == tenant_id,
                        CreditLedger.expires_at.is_not(None),
                        CreditLedger.expires_at <= now_ts,
                        CreditLedger.transaction_type.in_(
                            [
                                CreditTransactionType.PLAN_ALLOCATION.value,
                                CreditTransactionType.TOP_UP_PURCHASE.value,
                                CreditTransactionType.ADJUSTMENT.value,
                            ]
                        ),
                    )
                )
                if int(expiring_sum or 0) <= 0:
                    continue

                latest_balance = (
                    await session.execute(
                        select(CreditLedger)
                        .where(CreditLedger.tenant_id == tenant_id)
                        .order_by(CreditLedger.created_at.desc(), CreditLedger.id.desc())
                        .limit(1)
                    )
                ).scalar_one_or_none()
                current_balance = latest_balance.credits_balance_after if latest_balance else 0
                delta = -int(expiring_sum)
                next_balance = current_balance + delta

                await AuditWriter.insert_financial_record(
                    session,
                    model_class=CreditLedger,
                    tenant_id=tenant_id,
                    record_data={
                        "transaction_type": CreditTransactionType.EXPIRY.value,
                        "credits_delta": str(delta),
                        "reference_id": day_key,
                    },
                    values={
                        "transaction_type": CreditTransactionType.EXPIRY.value,
                        "credits_delta": delta,
                        "credits_balance_after": next_balance,
                        "reference_id": day_key,
                        "reference_type": "daily_expiry",
                        "description": "Daily expired credits adjustment",
                        "expires_at": None,
                    },
                )
                expired_entries += 1
            await session.commit()
        return {"expired_entries": expired_entries}

    return asyncio.run(_run())
