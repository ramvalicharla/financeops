from __future__ import annotations

import logging
import uuid
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import and_, func, select

from financeops.db.models.payment import (
    BillingInvoice,
    CreditLedger,
    GracePeriodLog,
    PaymentMethod,
    SubscriptionEvent,
    TenantSubscription,
)
from financeops.db.models.users import IamUser, UserRole
from financeops.db.session import AsyncSessionLocal
from financeops.modules.notifications.service import send_notification
from financeops.modules.payment.application.invoice_service import InvoiceService
from financeops.modules.payment.application.trial_service import TrialService
from financeops.modules.payment.domain.enums import CreditTransactionType, InvoiceStatus, PaymentProvider, SubscriptionStatus
from financeops.modules.payment.domain.schemas import PaymentProviderResult
from financeops.modules.payment.infrastructure.providers.registry import get_provider
from financeops.services.audit_writer import AuditWriter
from financeops.tasks.async_runner import run_async
from financeops.tasks.base_task import FinanceOpsTask
from financeops.tasks.celery_app import celery_app

log = logging.getLogger(__name__)

MAX_SUBSCRIPTION_PAYMENT_RETRIES = 3


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
    metadata: dict[str, Any] | None = None,
    cancel_at_period_end: bool | None = None,
    cancelled_at: datetime | None = None,
) -> TenantSubscription:
    next_metadata = dict(source.metadata_json or {}) if metadata is None else metadata
    next_cancel_at_period_end = source.cancel_at_period_end if cancel_at_period_end is None else cancel_at_period_end
    next_cancelled_at = cancelled_at if cancelled_at is not None else source.cancelled_at
    next_auto_renew = False if status == SubscriptionStatus.CANCELLED.value else not next_cancel_at_period_end
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
            "start_date": source.start_date or source.current_period_start,
            "end_date": source.end_date or source.current_period_end,
            "trial_end_date": source.trial_end_date or source.trial_end,
            "auto_renew": next_auto_renew,
            "cancelled_at": next_cancelled_at,
            "cancel_at_period_end": next_cancel_at_period_end,
            "onboarding_mode": source.onboarding_mode,
            "billing_country": source.billing_country,
            "billing_currency": source.billing_currency,
            "metadata_json": next_metadata,
        },
    )


def _payment_failure_result(
    *,
    error_code: str,
    error_message: str,
    raw_response: dict[str, Any] | None = None,
) -> PaymentProviderResult:
    return PaymentProviderResult(
        success=False,
        provider_id=None,
        raw_response=raw_response or {"error": error_message},
        error_code=error_code,
        error_message=error_message,
    )


async def _list_current_subscriptions(session) -> list[TenantSubscription]:
    rows = list(
        (
            await session.execute(
                select(TenantSubscription).order_by(TenantSubscription.created_at.desc(), TenantSubscription.id.desc())
            )
        ).scalars()
    )
    latest_by_subscription: dict[tuple[uuid.UUID, str], TenantSubscription] = {}
    for row in rows:
        key = (row.tenant_id, row.provider_subscription_id)
        if key not in latest_by_subscription:
            latest_by_subscription[key] = row
    return list(latest_by_subscription.values())


async def _get_retryable_invoice(
    *,
    session,
    source: TenantSubscription,
) -> BillingInvoice | None:
    return (
        await session.execute(
            select(BillingInvoice)
            .join(
                TenantSubscription,
                and_(
                    TenantSubscription.id == BillingInvoice.subscription_id,
                    TenantSubscription.tenant_id == BillingInvoice.tenant_id,
                ),
            )
            .where(
                BillingInvoice.tenant_id == source.tenant_id,
                TenantSubscription.provider_subscription_id == source.provider_subscription_id,
                BillingInvoice.status.in_([InvoiceStatus.OPEN.value, InvoiceStatus.UNCOLLECTIBLE.value]),
            )
            .order_by(BillingInvoice.created_at.desc(), BillingInvoice.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def _get_default_payment_method(
    *,
    session,
    source: TenantSubscription,
) -> PaymentMethod | None:
    return (
        await session.execute(
            select(PaymentMethod)
            .where(
                PaymentMethod.tenant_id == source.tenant_id,
                PaymentMethod.provider == source.provider,
                PaymentMethod.is_default.is_(True),
            )
            .order_by(PaymentMethod.created_at.desc(), PaymentMethod.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


def _next_retry_count(source: TenantSubscription) -> int:
    raw_value = (source.metadata_json or {}).get("payment_retry_count", 0)
    try:
        return int(raw_value) + 1
    except (TypeError, ValueError):
        return 1


def _build_retry_metadata(
    *,
    source: TenantSubscription,
    payment_result: PaymentProviderResult,
    retry_count: int,
    invoice: BillingInvoice | None,
    payment_method: PaymentMethod | None,
) -> dict[str, Any]:
    metadata = dict(source.metadata_json or {})
    metadata["payment_retry_count"] = retry_count
    metadata["payment_retry_last_attempt_at"] = datetime.now(UTC).isoformat()
    metadata["payment_retry_last_result"] = "success" if payment_result.success else "failed"
    if invoice is not None:
        metadata["payment_retry_last_invoice_id"] = invoice.provider_invoice_id
    if payment_method is not None:
        metadata["payment_retry_last_payment_method_id"] = payment_method.provider_payment_method_id
    if payment_result.provider_id:
        metadata["payment_retry_last_provider_id"] = payment_result.provider_id
    else:
        metadata.pop("payment_retry_last_provider_id", None)
    if payment_result.success:
        metadata["payment_retry_last_error"] = None
    else:
        metadata["payment_retry_last_error"] = payment_result.error_message or payment_result.error_code or "unknown_error"
    return metadata


async def _attempt_subscription_charge(
    *,
    session,
    source: TenantSubscription,
) -> tuple[PaymentProviderResult, BillingInvoice | None, PaymentMethod | None]:
    invoice = await _get_retryable_invoice(session=session, source=source)
    if invoice is None:
        return (
            _payment_failure_result(
                error_code="no_retryable_invoice",
                error_message="No open or uncollectible invoice found for subscription retry",
                raw_response={"provider_subscription_id": source.provider_subscription_id},
            ),
            None,
            None,
        )

    payment_method = await _get_default_payment_method(session=session, source=source)
    if payment_method is None:
        return (
            _payment_failure_result(
                error_code="no_default_payment_method",
                error_message="No default payment method found for payment retry",
                raw_response={"provider": source.provider},
            ),
            invoice,
            None,
        )

    try:
        provider = get_provider(PaymentProvider(source.provider))
    except ValueError:
        return (
            _payment_failure_result(
                error_code="unsupported_provider",
                error_message=f"Unsupported payment provider: {source.provider}",
                raw_response={"provider": source.provider},
            ),
            invoice,
            payment_method,
        )

    try:
        result = await provider.pay_invoice(
            invoice_id=invoice.provider_invoice_id,
            payment_method_id=payment_method.provider_payment_method_id,
        )
    except Exception as exc:  # pragma: no cover - defensive safety for provider SDK failures
        return (
            _payment_failure_result(
                error_code="provider_retry_exception",
                error_message=str(exc),
                raw_response={
                    "provider": source.provider,
                    "provider_invoice_id": invoice.provider_invoice_id,
                },
            ),
            invoice,
            payment_method,
        )
    return result, invoice, payment_method


async def _retry_failed_payments_async(session) -> dict[str, int]:
    reactivated = 0
    failed = 0
    cancelled = 0
    skipped = 0
    invoice_service = InvoiceService(session)

    current_rows = await _list_current_subscriptions(session)
    retry_candidates = [row for row in current_rows if row.status == SubscriptionStatus.PAST_DUE.value]

    for sub in retry_candidates:
        try:
            async with session.begin_nested():
                payment_result, invoice, payment_method = await _attempt_subscription_charge(session=session, source=sub)
                retry_count = 0 if payment_result.success else _next_retry_count(sub)
                metadata = _build_retry_metadata(
                    source=sub,
                    payment_result=payment_result,
                    retry_count=retry_count,
                    invoice=invoice,
                    payment_method=payment_method,
                )
                if payment_result.success:
                    if invoice is not None:
                        await invoice_service.mark_paid(
                            tenant_id=sub.tenant_id,
                            invoice_id=invoice.id,
                            payment_result=payment_result,
                        )
                    revised = await _append_subscription_revision(
                        session=session,
                        source=sub,
                        status=SubscriptionStatus.ACTIVE.value,
                        metadata=metadata,
                    )
                    await _emit_subscription_event(
                        session=session,
                        tenant_id=revised.tenant_id,
                        subscription_id=revised.id,
                        event_type="REACTIVATED",
                        from_status=sub.status,
                        to_status=revised.status,
                    )
                    log.info(
                        "Payment retry succeeded for tenant=%s subscription=%s provider=%s invoice=%s",
                        revised.tenant_id,
                        revised.provider_subscription_id,
                        revised.provider,
                        invoice.provider_invoice_id if invoice is not None else None,
                    )
                    reactivated += 1
                    continue

                should_cancel = retry_count >= MAX_SUBSCRIPTION_PAYMENT_RETRIES
                next_status = SubscriptionStatus.CANCELLED.value if should_cancel else SubscriptionStatus.PAST_DUE.value
                revised = await _append_subscription_revision(
                    session=session,
                    source=sub,
                    status=next_status,
                    metadata=metadata,
                    cancel_at_period_end=False if should_cancel else None,
                    cancelled_at=datetime.now(UTC) if should_cancel else None,
                )
                await _emit_subscription_event(
                    session=session,
                    tenant_id=revised.tenant_id,
                    subscription_id=revised.id,
                    event_type="CANCELLED" if should_cancel else "PAYMENT_RETRY_FAILED",
                    from_status=sub.status,
                    to_status=revised.status,
                )
                log.warning(
                    "Payment retry failed for tenant=%s subscription=%s provider=%s retry_count=%s error=%s",
                    revised.tenant_id,
                    revised.provider_subscription_id,
                    revised.provider,
                    retry_count,
                    payment_result.error_message or payment_result.error_code,
                )
                if should_cancel:
                    cancelled += 1
                else:
                    failed += 1
        except Exception:
            log.exception(
                "Unexpected payment retry failure for tenant=%s subscription=%s",
                sub.tenant_id,
                sub.provider_subscription_id,
            )
            failed += 1
            skipped += 1

    await session.commit()
    return {
        "reactivated": reactivated,
        "failed": failed,
        "cancelled": cancelled,
        "skipped": skipped,
    }


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

    return run_async(_run())


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

    return run_async(_run())


@celery_app.task(name="payment.retry_failed_payments", base=FinanceOpsTask)
def retry_failed_payments() -> dict[str, int]:
    async def _run() -> dict[str, int]:
        async with AsyncSessionLocal() as session:
            return await _retry_failed_payments_async(session)

    return run_async(_run())


@celery_app.task(name="payment.check_trial_expirations", base=FinanceOpsTask)
def check_trial_expirations() -> dict[str, int]:
    async def _run() -> dict[str, int]:
        converted = 0
        incomplete = 0
        today = date.today()

        async with AsyncSessionLocal() as session:
            # Fetch all trialing subscriptions whose trial window has closed.
            # Both trial_end_date and trial_end are set at subscription creation;
            # we prefer trial_end_date (more explicit) and fall back to trial_end.
            expired_subs: list[TenantSubscription] = list(
                (
                    await session.execute(
                        select(TenantSubscription).where(
                            TenantSubscription.status == SubscriptionStatus.TRIALING.value,
                            TenantSubscription.trial_end_date.is_not(None),
                            TenantSubscription.trial_end_date < today,
                        )
                    )
                ).scalars()
            )

            for sub in expired_subs:
                try:
                    async with session.begin_nested():
                        has_payment_method = (
                            await session.execute(
                                select(PaymentMethod.id).where(
                                    PaymentMethod.tenant_id == sub.tenant_id,
                                    PaymentMethod.is_default.is_(True),
                                ).limit(1)
                            )
                        ).scalar_one_or_none() is not None

                        trial_end_date = sub.trial_end_date or sub.trial_end
                        convert = TrialService.should_convert_to_active(
                            trial_end=trial_end_date,
                            has_payment_method=has_payment_method,
                            as_of=today,
                        )
                        mark_incomplete = TrialService.should_mark_incomplete(
                            trial_end=trial_end_date,
                            has_payment_method=has_payment_method,
                            as_of=today,
                        )

                        if not convert and not mark_incomplete:
                            continue

                        old_status = sub.status
                        if convert:
                            next_status = SubscriptionStatus.ACTIVE.value
                            event_type = "TRIAL_CONVERTED"
                            notif_title = "Your trial has been activated"
                            notif_body = "Your trial period has ended and your subscription is now active."
                            converted += 1
                        else:
                            next_status = SubscriptionStatus.INCOMPLETE.value
                            event_type = "TRIAL_EXPIRED"
                            notif_title = "Your trial has expired"
                            notif_body = (
                                "Your trial period has ended. Add a payment method to continue using FinanceOps."
                            )
                            incomplete += 1

                        revised = await _append_subscription_revision(
                            session=session,
                            source=sub,
                            status=next_status,
                        )
                        await _emit_subscription_event(
                            session=session,
                            tenant_id=sub.tenant_id,
                            subscription_id=revised.id,
                            event_type=event_type,
                            from_status=old_status,
                            to_status=next_status,
                        )

                        # Notify the tenant's primary user (finance_leader or first user found).
                        recipient = (
                            await session.execute(
                                select(IamUser).where(
                                    IamUser.tenant_id == sub.tenant_id,
                                    IamUser.role == UserRole.finance_leader.value,
                                    IamUser.is_active.is_(True),
                                ).limit(1)
                            )
                        ).scalar_one_or_none()

                        if recipient is None:
                            recipient = (
                                await session.execute(
                                    select(IamUser).where(
                                        IamUser.tenant_id == sub.tenant_id,
                                        IamUser.is_active.is_(True),
                                    ).limit(1)
                                )
                            ).scalar_one_or_none()

                        if recipient is not None:
                            await send_notification(
                                session,
                                tenant_id=sub.tenant_id,
                                recipient_user_id=recipient.id,
                                notification_type="trial_expiry",
                                title=notif_title,
                                body=notif_body,
                                metadata={"subscription_id": str(revised.id), "event": event_type},
                            )

                        log.info(
                            "trial_expiry_processed tenant=%s subscription=%s old_status=%s new_status=%s",
                            sub.tenant_id,
                            sub.provider_subscription_id,
                            old_status,
                            next_status,
                        )
                except Exception:
                    log.exception(
                        "trial_expiry_failed tenant=%s subscription=%s",
                        sub.tenant_id,
                        sub.provider_subscription_id,
                    )

            await session.commit()

        log.info(
            "trial_expiry_task_complete converted=%s incomplete=%s",
            converted,
            incomplete,
        )
        return {"converted": converted, "incomplete": incomplete}

    return run_async(_run())


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

    return run_async(_run())
