from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import (
    get_async_session,
    get_current_user,
    require_finance_leader,
)
from financeops.db.models.payment import BillingPlan, TenantSubscription
from financeops.db.models.users import IamUser
from financeops.modules.payment.application.billing_service import BillingService
from financeops.modules.payment.application.subscription_service import SubscriptionService
from financeops.modules.payment.domain.enums import BillingCycle, OnboardingMode, PaymentProvider
from financeops.services.audit_writer import AuditWriter
from financeops.shared_kernel.idempotency import require_idempotency_key
from financeops.shared_kernel.response import ok

router = APIRouter()


@router.post("/subscriptions")
async def create_subscription(
    request: Request,
    body: dict[str, Any],
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
    _: str = Depends(require_idempotency_key),
) -> dict:
    service = BillingService(session)
    row = await service.create_subscription(
        tenant_id=user.tenant_id,
        plan_id=uuid.UUID(str(body["plan_id"])),
        email=str(body["email"]),
        name=str(body["name"]),
        billing_country=str(body.get("billing_country", "IN")),
        billing_currency=str(body.get("billing_currency", "INR")),
        billing_cycle=BillingCycle(str(body.get("billing_cycle", "monthly"))),
        onboarding_mode=OnboardingMode(str(body.get("onboarding_mode", "self_serve"))),
        provider_override=PaymentProvider(str(body["provider_override"])) if body.get("provider_override") else None,
        metadata=dict(body.get("metadata", {})),
        created_by=user.id,
    )
    await session.flush()
    return ok(
        {
            "subscription_id": str(row.id),
            "status": row.status,
            "provider": row.provider,
            "provider_subscription_id": row.provider_subscription_id,
        },
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.get("/subscriptions/current")
async def get_current_subscription(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    service = SubscriptionService(session)
    row = await service.get_active_subscription_for_tenant(tenant_id=user.tenant_id)
    plan_payload: dict[str, Any] | None = None
    if row is not None:
        plan_row = (
            await session.execute(
                select(BillingPlan).where(
                    BillingPlan.tenant_id == user.tenant_id,
                    BillingPlan.id == row.plan_id,
                )
            )
        ).scalar_one_or_none()
        if plan_row is not None:
            plan_payload = {
                "id": str(plan_row.id),
                "name": plan_row.name,
                "plan_tier": plan_row.plan_tier,
                "pricing_type": plan_row.pricing_type,
                "price": str(plan_row.price) if plan_row.price is not None else None,
                "currency": plan_row.currency,
                "billing_cycle": plan_row.billing_cycle,
                "base_price_inr": str(plan_row.base_price_inr),
                "base_price_usd": str(plan_row.base_price_usd),
                "included_credits": plan_row.included_credits,
                "max_entities": plan_row.max_entities,
                "max_connectors": plan_row.max_connectors,
                "max_users": plan_row.max_users,
                "trial_days": plan_row.trial_days,
                "annual_discount_pct": str(plan_row.annual_discount_pct),
                "is_active": plan_row.is_active,
            }
    return ok(
        {
            "item": None
            if row is None
            else {
                "id": str(row.id),
                "plan_id": str(row.plan_id),
                "plan": plan_payload,
                "provider": row.provider,
                "status": row.status,
                "billing_cycle": row.billing_cycle,
                "current_period_start": row.current_period_start.isoformat(),
                "current_period_end": row.current_period_end.isoformat(),
                "trial_start": row.trial_start.isoformat() if row.trial_start else None,
                "trial_end": row.trial_end.isoformat() if row.trial_end else None,
                "start_date": row.start_date.isoformat() if row.start_date else None,
                "end_date": row.end_date.isoformat() if row.end_date else None,
                "trial_end_date": row.trial_end_date.isoformat() if row.trial_end_date else None,
                "auto_renew": row.auto_renew,
                "cancel_at_period_end": row.cancel_at_period_end,
                "billing_country": row.billing_country,
                "billing_currency": row.billing_currency,
                "metadata": row.metadata_json,
            },
        },
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.post("/subscriptions/upgrade")
async def upgrade_subscription(
    request: Request,
    body: dict[str, Any],
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
    _: str = Depends(require_idempotency_key),
) -> dict:
    service = BillingService(session)
    record = await service.upgrade_subscription(
        tenant_id=user.tenant_id,
        subscription_id=uuid.UUID(str(body["subscription_id"])),
        to_plan_id=uuid.UUID(str(body["to_plan_id"])),
        created_by=user.id,
        prorate=bool(body.get("prorate", True)),
    )
    await session.flush()
    return ok(
        {
            "proration_record_id": str(record.id),
            "credit_amount": str(record.credit_amount),
            "debit_amount": str(record.debit_amount),
            "net_adjustment": str(record.net_adjustment),
            "currency": record.currency,
        },
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.post("/subscriptions/cancel")
async def cancel_subscription(
    request: Request,
    body: dict[str, Any],
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
    _: str = Depends(require_idempotency_key),
) -> dict:
    service = BillingService(session)
    row = await service.cancel_subscription(
        tenant_id=user.tenant_id,
        subscription_id=uuid.UUID(str(body["subscription_id"])),
        cancel_at_period_end=bool(body.get("cancel_at_period_end", True)),
    )
    await session.flush()
    return ok(
        {
            "subscription_id": str(row.id),
            "status": row.status,
            "cancel_at_period_end": row.cancel_at_period_end,
        },
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.post("/subscriptions/reactivate")
async def reactivate_subscription(
    request: Request,
    body: dict[str, Any],
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
    _: str = Depends(require_idempotency_key),
) -> dict:
    service = BillingService(session)
    row = await service.reactivate_subscription(
        tenant_id=user.tenant_id,
        subscription_id=uuid.UUID(str(body["subscription_id"])),
    )
    await session.flush()
    return ok(
        {
            "subscription_id": str(row.id),
            "status": row.status,
        },
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.post("/admin/activate-tenant")
async def activate_tenant_billing(
    request: Request,
    body: dict[str, Any],
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
    _: str = Depends(require_idempotency_key),
) -> dict:
    tenant_id = uuid.UUID(str(body.get("tenant_id", user.tenant_id)))
    current = (
        await session.execute(
            select(TenantSubscription)
            .where(TenantSubscription.tenant_id == tenant_id)
            .order_by(TenantSubscription.created_at.desc(), TenantSubscription.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if current is not None:
        await AuditWriter.insert_financial_record(
            session,
            model_class=TenantSubscription,
            tenant_id=current.tenant_id,
            record_data={
                "plan_id": str(current.plan_id),
                "provider": current.provider,
                "provider_subscription_id": current.provider_subscription_id,
                "status": "active",
            },
            values={
                "plan_id": current.plan_id,
                "provider": current.provider,
                "provider_subscription_id": current.provider_subscription_id,
                "provider_customer_id": current.provider_customer_id,
                "status": "active",
                "billing_cycle": current.billing_cycle,
                "current_period_start": current.current_period_start,
                "current_period_end": current.current_period_end,
                "trial_start": current.trial_start,
                "trial_end": current.trial_end,
                "cancelled_at": current.cancelled_at,
                "cancel_at_period_end": current.cancel_at_period_end,
                "onboarding_mode": current.onboarding_mode,
                "billing_country": current.billing_country,
                "billing_currency": current.billing_currency,
                "metadata_json": dict(current.metadata_json or {}),
            },
        )
    await session.flush()
    return ok(
        {"tenant_id": str(tenant_id), "status": "active"},
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.post("/admin/override-provider")
async def override_provider(
    request: Request,
    body: dict[str, Any],
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
    _: str = Depends(require_idempotency_key),
) -> dict:
    subscription_id = uuid.UUID(str(body["subscription_id"]))
    provider = PaymentProvider(str(body["provider"]))
    current = (
        await session.execute(
            select(TenantSubscription).where(
                TenantSubscription.tenant_id == user.tenant_id,
                TenantSubscription.id == subscription_id,
            )
        )
    ).scalar_one()
    next_metadata = {
        **dict(current.metadata_json or {}),
        "provider_override": provider.value,
        "provider_override_at": datetime.now(UTC).isoformat(),
    }
    row = await AuditWriter.insert_financial_record(
        session,
        model_class=TenantSubscription,
        tenant_id=current.tenant_id,
        record_data={
            "plan_id": str(current.plan_id),
            "provider": current.provider,
            "provider_subscription_id": current.provider_subscription_id,
            "status": current.status,
            "provider_override": provider.value,
        },
        values={
            "plan_id": current.plan_id,
            "provider": current.provider,
            "provider_subscription_id": current.provider_subscription_id,
            "provider_customer_id": current.provider_customer_id,
            "status": current.status,
            "billing_cycle": current.billing_cycle,
            "current_period_start": current.current_period_start,
            "current_period_end": current.current_period_end,
            "trial_start": current.trial_start,
            "trial_end": current.trial_end,
            "cancelled_at": current.cancelled_at,
            "cancel_at_period_end": current.cancel_at_period_end,
            "onboarding_mode": current.onboarding_mode,
            "billing_country": current.billing_country,
            "billing_currency": current.billing_currency,
            "metadata_json": next_metadata,
        },
    )
    await session.flush()
    return ok(
        {"subscription_id": str(row.id), "provider_override": provider.value},
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")
