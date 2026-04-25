from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user
from financeops.db.models.payment import BillingPlan
from financeops.db.models.users import IamUser
from financeops.shared_kernel.response import ok

router = APIRouter()
PLATFORM_PLAN_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000000")


@router.get("/plans")
async def list_billing_plans(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    rows = list(
        (
            await session.execute(
                select(BillingPlan)
                .where(
                    BillingPlan.tenant_id.in_(
                        [user.tenant_id, PLATFORM_PLAN_TENANT_ID]
                    )
                )
                .order_by(BillingPlan.created_at.desc(), BillingPlan.id.desc())
            )
        ).scalars()
    )
    return ok(
        {
            "items": [
                {
                    "id": str(row.id),
                    "name": row.name,
                    "plan_tier": row.plan_tier,
                    "pricing_type": row.pricing_type,
                    "price": str(row.price) if row.price is not None else None,
                    "currency": row.currency,
                    "billing_cycle": row.billing_cycle,
                    "base_price_inr": str(row.base_price_inr),
                    "base_price_usd": str(row.base_price_usd),
                    "included_credits": row.included_credits,
                    "trial_days": row.trial_days,
                    "annual_discount_pct": str(row.annual_discount_pct),
                    "is_active": row.is_active,
                }
                for row in rows
            ]
        },
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.get("/plans/{id}")
async def get_billing_plan(
    request: Request,
    id: str,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    row = (
        await session.execute(
            select(BillingPlan).where(
                BillingPlan.tenant_id.in_(
                    [user.tenant_id, PLATFORM_PLAN_TENANT_ID]
                ),
                BillingPlan.id == uuid.UUID(id),
            )
        )
    ).scalar_one()
    return ok(
        {
            "id": str(row.id),
            "name": row.name,
            "plan_tier": row.plan_tier,
            "pricing_type": row.pricing_type,
            "price": str(row.price) if row.price is not None else None,
            "currency": row.currency,
            "billing_cycle": row.billing_cycle,
            "base_price_inr": str(row.base_price_inr),
            "base_price_usd": str(row.base_price_usd),
            "included_credits": row.included_credits,
            "max_entities": row.max_entities,
            "max_connectors": row.max_connectors,
            "max_users": row.max_users,
            "modules_enabled": row.modules_enabled,
            "trial_days": row.trial_days,
            "annual_discount_pct": str(row.annual_discount_pct),
            "valid_from": row.valid_from.isoformat(),
            "valid_until": row.valid_until.isoformat() if row.valid_until else None,
            "is_active": row.is_active,
        },
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")
