from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user
from financeops.db.models.payment import TenantSubscription
from financeops.db.models.users import IamUser
from financeops.modules.payment.domain.enums import PaymentProvider
from financeops.modules.payment.infrastructure.providers.registry import get_provider
from financeops.shared_kernel.response import ok

router = APIRouter()


@router.get("/portal")
async def get_billing_portal(
    request: Request,
    return_url: str,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    subscription = (
        await session.execute(
            select(TenantSubscription)
            .where(TenantSubscription.tenant_id == user.tenant_id)
            .order_by(TenantSubscription.created_at.desc(), TenantSubscription.id.desc())
            .limit(1)
        )
    ).scalar_one()
    provider = get_provider(PaymentProvider(subscription.provider))
    portal_url = await provider.get_billing_portal_url(
        customer_id=subscription.provider_customer_id,
        return_url=return_url,
    )
    return ok(
        {"url": portal_url},
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")
