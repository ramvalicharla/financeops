from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user
from financeops.db.models.payment import PaymentMethod, TenantSubscription
from financeops.db.models.users import IamUser
from financeops.modules.payment.domain.enums import PaymentProvider
from financeops.modules.payment.infrastructure.providers.registry import get_provider
from financeops.services.audit_writer import AuditWriter
from financeops.shared_kernel.idempotency import require_idempotency_key
from financeops.shared_kernel.response import ok

router = APIRouter()


@router.get("/payment-methods")
async def list_payment_methods(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    rows = list(
        (
            await session.execute(
                select(PaymentMethod)
                .where(PaymentMethod.tenant_id == user.tenant_id)
                .order_by(PaymentMethod.created_at.desc(), PaymentMethod.id.desc())
            )
        ).scalars()
    )
    return ok(
        {
            "items": [
                {
                    "id": str(row.id),
                    "provider": row.provider,
                    "type": row.type,
                    "last4": row.last4,
                    "brand": row.brand,
                    "expiry_month": row.expiry_month,
                    "expiry_year": row.expiry_year,
                    "is_default": row.is_default,
                }
                for row in rows
            ]
        },
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.post("/payment-methods")
async def create_payment_method(
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
    provider_result = await provider_impl.create_payment_method(
        customer_id=subscription.provider_customer_id,
        payment_method_token=str(body["payment_method_token"]),
    )

    row = await AuditWriter.insert_financial_record(
        session,
        model_class=PaymentMethod,
        tenant_id=user.tenant_id,
        record_data={
            "provider": subscription.provider,
            "provider_payment_method_id": provider_result.provider_id or "",
            "type": str(body.get("type", "card")),
        },
        values={
            "provider": subscription.provider,
            "provider_payment_method_id": provider_result.provider_id or str(uuid.uuid4()),
            "type": str(body.get("type", "card")),
            "last4": body.get("last4"),
            "brand": body.get("brand"),
            "expiry_month": body.get("expiry_month"),
            "expiry_year": body.get("expiry_year"),
            "is_default": bool(body.get("is_default", False)),
            "billing_details": dict(body.get("billing_details", {})),
        },
    )
    await session.flush()
    return ok(
        {"payment_method_id": str(row.id), "provider_result": provider_result.model_dump(mode="json")},
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.delete("/payment-methods/{id}")
async def delete_payment_method(
    request: Request,
    id: str,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    from fastapi import HTTPException

    current = (
        await session.execute(
            select(PaymentMethod).where(
                PaymentMethod.tenant_id == user.tenant_id,
                PaymentMethod.id == uuid.UUID(id),
            )
        )
    ).scalar_one_or_none()
    if current is None:
        raise HTTPException(status_code=404, detail="Payment method not found")
    if current.is_default:
        raise HTTPException(status_code=400, detail="Cannot delete the default payment method")

    provider_impl = get_provider(PaymentProvider(current.provider))
    await provider_impl.detach_payment_method(current.provider_payment_method_id)

    await AuditWriter.insert_financial_record(
        session,
        model_class=PaymentMethod,
        tenant_id=user.tenant_id,
        record_data={
            "provider": current.provider,
            "provider_payment_method_id": current.provider_payment_method_id,
            "deactivated": "true",
        },
        values={
            "provider": current.provider,
            "provider_payment_method_id": current.provider_payment_method_id,
            "type": current.type,
            "last4": current.last4,
            "brand": current.brand,
            "expiry_month": current.expiry_month,
            "expiry_year": current.expiry_year,
            "is_default": False,
            "billing_details": {**(current.billing_details or {}), "deactivated": True},
        },
    )
    await session.flush()
    return ok(
        {"success": True},
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.post("/payment-methods/{id}/set-default")
async def set_default_payment_method(
    request: Request,
    id: str,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
    _: str = Depends(require_idempotency_key),
) -> dict:
    current = (
        await session.execute(
            select(PaymentMethod).where(
                PaymentMethod.tenant_id == user.tenant_id,
                PaymentMethod.id == uuid.UUID(id),
            )
        )
    ).scalar_one()
    row = await AuditWriter.insert_financial_record(
        session,
        model_class=PaymentMethod,
        tenant_id=current.tenant_id,
        record_data={
            "provider": current.provider,
            "provider_payment_method_id": current.provider_payment_method_id,
            "set_default": "true",
        },
        values={
            "provider": current.provider,
            "provider_payment_method_id": current.provider_payment_method_id,
            "type": current.type,
            "last4": current.last4,
            "brand": current.brand,
            "expiry_month": current.expiry_month,
            "expiry_year": current.expiry_year,
            "is_default": True,
            "billing_details": dict(current.billing_details or {}),
        },
    )
    await session.flush()
    return ok(
        {"payment_method_id": str(row.id), "is_default": row.is_default},
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")
