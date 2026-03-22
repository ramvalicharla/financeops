from __future__ import annotations

from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user, require_finance_leader
from financeops.db.models.payment import CreditLedger, TenantSubscription
from financeops.db.models.users import IamUser
from financeops.modules.payment.application.credit_service import CreditService
from financeops.modules.payment.domain.enums import PaymentProvider
from financeops.modules.payment.infrastructure.providers.registry import get_provider
from financeops.shared_kernel.idempotency import require_idempotency_key
from financeops.shared_kernel.response import ok

router = APIRouter()


@router.get("/credits/balance")
async def get_credit_balance(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    service = CreditService(session)
    balance = await service.get_balance(tenant_id=user.tenant_id)
    return ok(
        {"balance": balance},
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.get("/credits/ledger")
async def get_credit_ledger(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    rows = list(
        (
            await session.execute(
                select(CreditLedger)
                .where(CreditLedger.tenant_id == user.tenant_id)
                .order_by(CreditLedger.created_at.desc(), CreditLedger.id.desc())
            )
        ).scalars()
    )
    return ok(
        {
            "items": [
                {
                    "id": str(row.id),
                    "transaction_type": row.transaction_type,
                    "credits_delta": row.credits_delta,
                    "credits_balance_after": row.credits_balance_after,
                    "reference_id": row.reference_id,
                    "reference_type": row.reference_type,
                    "description": row.description,
                    "expires_at": row.expires_at.isoformat() if row.expires_at else None,
                }
                for row in rows
            ]
        },
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.post("/credits/top-up")
async def top_up_credits(
    request: Request,
    body: dict[str, Any],
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
    _: str = Depends(require_idempotency_key),
) -> dict:
    subscription = (
        await session.execute(
            select(TenantSubscription)
            .where(TenantSubscription.tenant_id == user.tenant_id)
            .order_by(TenantSubscription.created_at.desc(), TenantSubscription.id.desc())
            .limit(1)
        )
    ).scalar_one()
    provider_impl = get_provider(PaymentProvider(subscription.provider))
    credits = int(body["credits"])
    amount = Decimal(str(body["amount"]))
    payment_result = await provider_impl.create_top_up_charge(
        customer_id=subscription.provider_customer_id,
        amount=amount,
        currency=str(body.get("currency", subscription.billing_currency)).upper(),
        credits=credits,
        metadata=dict(body.get("metadata", {})),
    )
    service = CreditService(session)
    ledger = await service.purchase_top_up(
        tenant_id=user.tenant_id,
        credits=credits,
        payment_result=payment_result,
        amount_charged=amount,
        currency=str(body.get("currency", subscription.billing_currency)).upper(),
        provider=subscription.provider,
        created_by=user.id,
    )
    await session.flush()
    return ok(
        {
            "credit_ledger_id": str(ledger.id),
            "credits_balance_after": ledger.credits_balance_after,
            "provider_result": payment_result.model_dump(mode="json"),
        },
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.post("/admin/adjust-credits")
async def adjust_credits(
    request: Request,
    body: dict[str, Any],
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
    _: str = Depends(require_idempotency_key),
) -> dict:
    service = CreditService(session)
    ledger = await service.consume_credits(
        tenant_id=user.tenant_id,
        credits=int(body.get("credits", 0)),
        reference_id=str(body.get("reference_id", "manual_adjustment")),
        reference_type="admin_adjustment",
        created_by=user.id,
    )
    await session.flush()
    return ok(
        {
            "credit_ledger_id": str(ledger.id),
            "credits_balance_after": ledger.credits_balance_after,
        },
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")
