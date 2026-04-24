from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import (
    get_async_session,
    get_current_user,
    require_platform_admin,
    require_platform_owner,
)
from financeops.core.security import create_access_token
from financeops.db.models.payment import (
    BillingInvoice,
    BillingPlan,
    CreditLedger,
    TenantSubscription,
)
from financeops.db.models.tenants import IamTenant
from financeops.db.models.users import IamUser
from financeops.modules.payment.application.credit_service import CreditService
from financeops.modules.payment.application.subscription_service import SubscriptionService
from financeops.modules.payment.domain.enums import CreditTransactionType
from financeops.services.audit_service import log_action
from financeops.services.audit_writer import AuditWriter

router = APIRouter()

# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------


class ExtendTrialRequest(BaseModel):
    days: int = Field(..., ge=1, le=90)


class ChangePlanRequest(BaseModel):
    plan_id: uuid.UUID


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_request_ip(request: Request) -> str | None:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    client = request.client
    return client.host if client else None


async def _get_latest_subscription(
    session: AsyncSession,
    tenant_id: uuid.UUID,
) -> TenantSubscription | None:
    return (
        await session.execute(
            select(TenantSubscription)
            .where(TenantSubscription.tenant_id == tenant_id)
            .order_by(TenantSubscription.created_at.desc(), TenantSubscription.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def _get_credit_balance(session: AsyncSession, tenant_id: uuid.UUID) -> int:
    total = await session.scalar(
        select(func.coalesce(func.sum(CreditLedger.credits_delta), 0)).where(
            CreditLedger.tenant_id == tenant_id,
            CreditLedger.expires_at.is_(None)
            | (CreditLedger.expires_at >= datetime.now(UTC)),
        )
    )
    return int(total or 0)


# ---------------------------------------------------------------------------
# 1. GET /platform/admin/tenants
# ---------------------------------------------------------------------------


@router.get("/tenants", tags=["Platform Admin"])
async def admin_list_tenants(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_platform_admin),
) -> dict[str, Any]:
    total = int(
        (
            await session.execute(
                select(func.count()).select_from(IamTenant)
            )
        ).scalar_one()
    )
    tenants = (
        await session.execute(
            select(IamTenant)
            .order_by(IamTenant.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
    ).scalars().all()

    items = []
    for t in tenants:
        sub = await _get_latest_subscription(session, t.id)
        balance = await _get_credit_balance(session, t.id)
        user_count = int(
            (
                await session.execute(
                    select(func.count()).select_from(IamUser).where(IamUser.tenant_id == t.id)
                )
            ).scalar_one()
        )
        items.append(
            {
                "id": str(t.id),
                "name": t.display_name,
                "slug": t.slug,
                "status": t.status.value if hasattr(t.status, "value") else str(t.status),
                "plan_tier": sub.plan_id and str(sub.plan_id) if sub else None,
                "trial_end_date": (
                    sub.trial_end_date.isoformat() if sub and sub.trial_end_date else None
                ),
                "credit_balance": balance,
                "user_count": user_count,
                "created_at": t.created_at.isoformat(),
            }
        )

    return {"items": items, "total": total, "limit": limit, "offset": offset}


# ---------------------------------------------------------------------------
# 2. GET /platform/admin/tenants/{tenant_id}
# ---------------------------------------------------------------------------


@router.get("/tenants/{tenant_id}", tags=["Platform Admin"])
async def admin_get_tenant(
    tenant_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_platform_admin),
) -> dict[str, Any]:
    tenant = (
        await session.execute(select(IamTenant).where(IamTenant.id == tenant_id))
    ).scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")

    sub = await _get_latest_subscription(session, tenant_id)
    balance = await _get_credit_balance(session, tenant_id)

    recent_invoices = (
        await session.execute(
            select(BillingInvoice)
            .where(BillingInvoice.tenant_id == tenant_id)
            .order_by(BillingInvoice.created_at.desc())
            .limit(5)
        )
    ).scalars().all()

    recent_credits = (
        await session.execute(
            select(CreditLedger)
            .where(CreditLedger.tenant_id == tenant_id)
            .order_by(CreditLedger.created_at.desc())
            .limit(10)
        )
    ).scalars().all()

    return {
        "tenant": {
            "id": str(tenant.id),
            "name": tenant.display_name,
            "slug": tenant.slug,
            "status": tenant.status.value if hasattr(tenant.status, "value") else str(tenant.status),
            "country": tenant.country,
            "created_at": tenant.created_at.isoformat(),
        },
        "subscription": (
            {
                "id": str(sub.id),
                "plan_id": str(sub.plan_id),
                "status": sub.status,
                "billing_cycle": sub.billing_cycle,
                "trial_end_date": sub.trial_end_date.isoformat() if sub.trial_end_date else None,
                "current_period_start": sub.current_period_start.isoformat(),
                "current_period_end": sub.current_period_end.isoformat(),
            }
            if sub
            else None
        ),
        "credit_balance": balance,
        "recent_invoices": [
            {
                "id": str(inv.id),
                "status": inv.status,
                "total": str(inv.total),
                "currency": inv.currency,
                "due_date": inv.due_date.isoformat(),
                "created_at": inv.created_at.isoformat(),
            }
            for inv in recent_invoices
        ],
        "recent_credits": [
            {
                "id": str(cr.id),
                "transaction_type": cr.transaction_type,
                "credits_delta": cr.credits_delta,
                "credits_balance_after": cr.credits_balance_after,
                "created_at": cr.created_at.isoformat(),
            }
            for cr in recent_credits
        ],
    }


# ---------------------------------------------------------------------------
# 3. POST /platform/admin/tenants/{tenant_id}/extend-trial
# ---------------------------------------------------------------------------


@router.post("/tenants/{tenant_id}/extend-trial", tags=["Platform Admin"])
async def admin_extend_trial(
    tenant_id: uuid.UUID,
    body: ExtendTrialRequest,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_platform_admin),
) -> dict[str, Any]:
    sub = await _get_latest_subscription(session, tenant_id)
    if sub is None:
        raise HTTPException(status_code=404, detail="No subscription found for tenant")
    if sub.status != "trialing":
        raise HTTPException(status_code=400, detail="Subscription is not in trial status")

    current_end = sub.trial_end_date or sub.trial_end or date.today()
    new_end = current_end + timedelta(days=body.days)

    svc = SubscriptionService(session)
    revised = await svc.append_subscription_revision(
        source=sub,
        metadata={**(sub.metadata_json or {}), "trial_extended_by": body.days, "trial_extended_at": datetime.now(UTC).isoformat()},
    )
    # Patch trial_end_date directly via a second revision that carries the new date
    await AuditWriter.insert_financial_record(
        session,
        model_class=TenantSubscription,
        tenant_id=tenant_id,
        record_data={
            "plan_id": str(sub.plan_id),
            "provider": sub.provider,
            "provider_subscription_id": sub.provider_subscription_id,
            "status": sub.status,
            "trial_end_date": new_end.isoformat(),
            "admin_action": "extend_trial",
        },
        values={
            "plan_id": sub.plan_id,
            "provider": sub.provider,
            "provider_subscription_id": sub.provider_subscription_id,
            "provider_customer_id": sub.provider_customer_id,
            "status": sub.status,
            "billing_cycle": sub.billing_cycle,
            "current_period_start": sub.current_period_start,
            "current_period_end": new_end,
            "trial_start": sub.trial_start,
            "trial_end": new_end,
            "start_date": sub.start_date or sub.current_period_start,
            "end_date": new_end,
            "trial_end_date": new_end,
            "auto_renew": sub.auto_renew,
            "cancelled_at": sub.cancelled_at,
            "cancel_at_period_end": sub.cancel_at_period_end,
            "onboarding_mode": sub.onboarding_mode,
            "billing_country": sub.billing_country,
            "billing_currency": sub.billing_currency,
            "metadata_json": {**(sub.metadata_json or {}), "trial_extended_by": body.days},
        },
    )
    await log_action(
        session,
        tenant_id=user.tenant_id,
        user_id=user.id,
        action="admin.trial.extended",
        resource_type="tenant_subscription",
        resource_id=str(sub.id),
        new_value={"target_tenant_id": str(tenant_id), "days": body.days, "new_trial_end": new_end.isoformat()},
        ip_address=_get_request_ip(request),
    )
    await session.flush()
    return {"success": True, "new_trial_end_date": new_end.isoformat(), "days_added": body.days}


# ---------------------------------------------------------------------------
# 4. POST /platform/admin/tenants/{tenant_id}/activate
# ---------------------------------------------------------------------------


@router.post("/tenants/{tenant_id}/activate", tags=["Platform Admin"])
async def admin_activate_tenant(
    tenant_id: uuid.UUID,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_platform_admin),
) -> dict[str, Any]:
    sub = await _get_latest_subscription(session, tenant_id)
    if sub is None:
        raise HTTPException(status_code=404, detail="No subscription found for tenant")

    svc = SubscriptionService(session)
    revised = await svc.append_subscription_revision(source=sub, status="active")
    await log_action(
        session,
        tenant_id=user.tenant_id,
        user_id=user.id,
        action="admin.subscription.activated",
        resource_type="tenant_subscription",
        resource_id=str(sub.id),
        new_value={"target_tenant_id": str(tenant_id), "old_status": sub.status, "new_status": "active"},
        ip_address=_get_request_ip(request),
    )
    await session.flush()
    return {"success": True, "subscription_id": str(revised.id), "status": revised.status}


# ---------------------------------------------------------------------------
# 5. POST /platform/admin/tenants/{tenant_id}/suspend
# ---------------------------------------------------------------------------


@router.post("/tenants/{tenant_id}/suspend", tags=["Platform Admin"])
async def admin_suspend_tenant(
    tenant_id: uuid.UUID,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_platform_admin),
) -> dict[str, Any]:
    sub = await _get_latest_subscription(session, tenant_id)
    if sub is None:
        raise HTTPException(status_code=404, detail="No subscription found for tenant")

    svc = SubscriptionService(session)
    revised = await svc.append_subscription_revision(source=sub, status="suspended")
    await log_action(
        session,
        tenant_id=user.tenant_id,
        user_id=user.id,
        action="admin.subscription.suspended",
        resource_type="tenant_subscription",
        resource_id=str(sub.id),
        new_value={"target_tenant_id": str(tenant_id), "old_status": sub.status, "new_status": "suspended"},
        ip_address=_get_request_ip(request),
    )
    await session.flush()
    return {"success": True, "subscription_id": str(revised.id), "status": revised.status}


# ---------------------------------------------------------------------------
# 6. POST /platform/admin/tenants/{tenant_id}/change-plan
# ---------------------------------------------------------------------------


@router.post("/tenants/{tenant_id}/change-plan", tags=["Platform Admin"])
async def admin_change_plan(
    tenant_id: uuid.UUID,
    body: ChangePlanRequest,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_platform_admin),
) -> dict[str, Any]:
    plan = (
        await session.execute(
            select(BillingPlan).where(BillingPlan.id == body.plan_id)
        )
    ).scalar_one_or_none()
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")

    sub = await _get_latest_subscription(session, tenant_id)
    if sub is None:
        raise HTTPException(status_code=404, detail="No subscription found for tenant")

    old_plan_id = sub.plan_id
    svc = SubscriptionService(session)
    revised = await svc.append_subscription_revision(source=sub, plan_id=body.plan_id, status="active")

    # Allocate credits for new plan
    current_balance = await _get_credit_balance(session, tenant_id)
    next_balance = current_balance + int(plan.included_credits)
    await AuditWriter.insert_financial_record(
        session,
        model_class=CreditLedger,
        tenant_id=tenant_id,
        record_data={
            "transaction_type": CreditTransactionType.PLAN_ALLOCATION.value,
            "credits_delta": str(plan.included_credits),
            "plan_id": str(plan.id),
        },
        values={
            "transaction_type": CreditTransactionType.PLAN_ALLOCATION.value,
            "credits_delta": int(plan.included_credits),
            "credits_balance_after": next_balance,
            "reference_id": str(plan.id),
            "reference_type": "billing_plan",
            "description": f"Admin plan change to {plan.plan_tier}",
            "expires_at": None,
        },
    )
    await log_action(
        session,
        tenant_id=user.tenant_id,
        user_id=user.id,
        action="admin.subscription.plan_changed",
        resource_type="tenant_subscription",
        resource_id=str(sub.id),
        new_value={
            "target_tenant_id": str(tenant_id),
            "old_plan_id": str(old_plan_id),
            "new_plan_id": str(body.plan_id),
            "new_plan_tier": plan.plan_tier,
            "credits_allocated": int(plan.included_credits),
        },
        ip_address=_get_request_ip(request),
    )
    await session.flush()
    return {
        "success": True,
        "subscription_id": str(revised.id),
        "plan_id": str(body.plan_id),
        "plan_tier": plan.plan_tier,
        "credits_allocated": int(plan.included_credits),
    }


# ---------------------------------------------------------------------------
# 7. GET /platform/admin/credits
# ---------------------------------------------------------------------------


@router.get("/credits", tags=["Platform Admin"])
async def admin_list_credits(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    low_balance: bool = Query(default=False),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_platform_admin),
) -> dict[str, Any]:
    # Aggregate credit balances per tenant from the ledger
    balance_subq = (
        select(
            CreditLedger.tenant_id,
            func.coalesce(func.sum(CreditLedger.credits_delta), 0).label("balance"),
            func.max(CreditLedger.created_at).label("last_transaction_at"),
        )
        .where(
            CreditLedger.expires_at.is_(None)
            | (CreditLedger.expires_at >= datetime.now(UTC))
        )
        .group_by(CreditLedger.tenant_id)
        .subquery()
    )

    stmt = select(
        IamTenant.id,
        IamTenant.display_name,
        balance_subq.c.balance,
        balance_subq.c.last_transaction_at,
    ).outerjoin(balance_subq, IamTenant.id == balance_subq.c.tenant_id)

    if low_balance:
        stmt = stmt.where(
            (balance_subq.c.balance < 100) | balance_subq.c.balance.is_(None)
        )

    total = int(
        (
            await session.execute(select(func.count()).select_from(stmt.subquery()))
        ).scalar_one()
    )
    rows = (
        await session.execute(
            stmt.order_by(balance_subq.c.balance.asc().nulls_first()).offset(offset).limit(limit)
        )
    ).all()

    return {
        "items": [
            {
                "tenant_id": str(row.id),
                "tenant_name": row.display_name,
                "credit_balance": int(row.balance or 0),
                "last_transaction_at": row.last_transaction_at.isoformat() if row.last_transaction_at else None,
            }
            for row in rows
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


# ---------------------------------------------------------------------------
# 8. POST /platform/admin/tenants/{tenant_id}/switch
# ---------------------------------------------------------------------------


@router.post("/tenants/{tenant_id}/switch", tags=["Platform Admin"])
async def admin_switch_tenant(
    tenant_id: uuid.UUID,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_platform_owner),
) -> dict[str, Any]:
    tenant = (
        await session.execute(select(IamTenant).where(IamTenant.id == tenant_id))
    ).scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")

    # Issue a short-lived (15 min) JWT scoped to the target tenant.
    # The token carries the platform owner's user_id but the target tenant_id,
    # enabling read access into that org's context via the normal auth path.
    switch_token = create_access_token(
        user_id=user.id,
        tenant_id=tenant_id,
        role=user.role.value if hasattr(user.role, "value") else str(user.role),
        additional_claims={"scope": "platform_switch", "switched_by": str(user.id)},
        expires_delta=timedelta(minutes=15),
    )
    await log_action(
        session,
        tenant_id=user.tenant_id,
        user_id=user.id,
        action="admin.tenant.switched",
        resource_type="iam_tenant",
        resource_id=str(tenant_id),
        new_value={"target_tenant_id": str(tenant_id), "target_tenant_name": tenant.display_name},
        ip_address=_get_request_ip(request),
    )
    await session.flush()
    return {
        "switch_token": switch_token,
        "tenant_id": str(tenant_id),
        "tenant_name": tenant.display_name,
        "expires_in_seconds": 900,
    }
