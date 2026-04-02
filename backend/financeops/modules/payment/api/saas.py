from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user
from financeops.db.models.users import IamUser
from financeops.db.rls import clear_tenant_context, set_tenant_context
from financeops.db.session import AsyncSessionLocal
from financeops.modules.payment.application.entitlement_service import EntitlementService
from financeops.modules.payment.application.saas_billing_service import SaaSBillingService
from financeops.modules.payment.domain.enums import PaymentProvider
from financeops.shared_kernel.idempotency import require_idempotency_key
from financeops.shared_kernel.response import ok

router = APIRouter()
public_router = APIRouter()


class GenerateInvoiceRequest(BaseModel):
    subscription_id: uuid.UUID | None = None
    due_in_days: int = Field(default=7, ge=0, le=90)


class CheckoutRequest(BaseModel):
    return_url: str = Field(min_length=1, max_length=1024)


class UsageRecordRequest(BaseModel):
    feature_name: str = Field(min_length=1, max_length=128)
    usage_quantity: int = Field(default=1, ge=1)
    reference_type: str | None = Field(default=None, max_length=64)
    reference_id: str | None = Field(default=None, max_length=255)


class GenericWebhookRequest(BaseModel):
    provider: PaymentProvider | None = None
    tenant_id: uuid.UUID | None = None


@router.post("/generate-invoice")
async def generate_invoice(
    request: Request,
    body: GenerateInvoiceRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
    _: str = Depends(require_idempotency_key),
) -> dict:
    service = SaaSBillingService(session)
    row = await service.generate_invoice(
        tenant_id=user.tenant_id,
        actor_user_id=user.id,
        subscription_id=body.subscription_id,
        due_in_days=body.due_in_days,
    )
    await session.flush()
    return ok(
        {
            "invoice_id": str(row.id),
            "status": row.status,
            "currency": row.currency,
            "amount": str(row.amount or row.total),
            "due_date": row.due_date.isoformat(),
        },
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.post("/checkout")
async def create_checkout_session(
    request: Request,
    body: CheckoutRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    service = SaaSBillingService(session)
    payload = await service.create_checkout_session(
        tenant_id=user.tenant_id,
        return_url=body.return_url,
    )
    return ok(
        payload,
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.get("/entitlements/current")
async def get_current_entitlements(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    service = EntitlementService(session)
    rows = await service.list_latest_tenant_entitlements(tenant_id=user.tenant_id)
    if not rows:
        await service.refresh_tenant_entitlements(tenant_id=user.tenant_id, actor_user_id=user.id)
        rows = await service.list_latest_tenant_entitlements(tenant_id=user.tenant_id)
    return ok(
        {
            "items": [
                {
                    "id": str(row.id),
                    "feature_name": row.feature_name,
                    "access_type": row.access_type,
                    "effective_limit": row.effective_limit,
                    "source": row.source,
                    "source_reference_id": str(row.source_reference_id) if row.source_reference_id else None,
                    "metadata": row.metadata_json,
                }
                for row in rows
            ]
        },
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.post("/entitlements/refresh")
async def refresh_entitlements(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    service = EntitlementService(session)
    rows = await service.refresh_tenant_entitlements(
        tenant_id=user.tenant_id,
        actor_user_id=user.id,
    )
    await session.flush()
    return ok(
        {
            "inserted": len(rows),
            "features": [row.feature_name for row in rows],
        },
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.post("/usage/record")
async def record_usage(
    request: Request,
    body: UsageRecordRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    service = EntitlementService(session)
    decision = await service.check_entitlement(
        tenant_id=user.tenant_id,
        feature_name=body.feature_name,
        quantity=body.usage_quantity,
    )
    if not decision.allowed:
        return ok(
            {
                "allowed": False,
                "reason": decision.reason,
                "feature_name": decision.feature_name,
                "effective_limit": decision.effective_limit,
                "used": decision.used,
            },
            request_id=getattr(request.state, "request_id", None),
        ).model_dump(mode="json")

    row = await service.record_usage_event(
        tenant_id=user.tenant_id,
        feature_name=body.feature_name,
        usage_quantity=body.usage_quantity,
        reference_type=body.reference_type,
        reference_id=body.reference_id,
        actor_user_id=user.id,
    )
    await session.flush()
    return ok(
        {
            "allowed": True,
            "usage_event_id": str(row.id),
            "feature_name": row.feature_name,
            "usage_quantity": row.usage_quantity,
            "event_time": row.event_time.isoformat(),
        },
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.get("/usage")
async def get_usage_summary(
    request: Request,
    period_start: date | None = None,
    period_end: date | None = None,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    service = EntitlementService(session)
    rows = await service.list_latest_usage_aggregates(tenant_id=user.tenant_id)
    if period_start is not None:
        rows = [row for row in rows if row.period_start >= period_start]
    if period_end is not None:
        rows = [row for row in rows if row.period_end <= period_end]
    return ok(
        {
            "items": [
                {
                    "id": str(row.id),
                    "feature_name": row.feature_name,
                    "period_start": row.period_start.isoformat(),
                    "period_end": row.period_end.isoformat(),
                    "total_usage": row.total_usage,
                    "last_event_id": str(row.last_event_id) if row.last_event_id else None,
                }
                for row in rows
            ]
        },
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@public_router.post("/webhook")
async def generic_webhook(
    request: Request,
    body: GenericWebhookRequest | None = None,
    provider: PaymentProvider | None = None,
    tenant_id: uuid.UUID | None = None,
) -> dict:
    resolved_provider = body.provider if body and body.provider else provider
    resolved_tenant_id = body.tenant_id if body and body.tenant_id else tenant_id
    if resolved_provider is None or resolved_tenant_id is None:
        return ok(
            {"accepted": False, "reason": "provider_and_tenant_id_required"},
            request_id=getattr(request.state, "request_id", None),
        ).model_dump(mode="json")
    payload_bytes = await request.body()
    signature = request.headers.get("Stripe-Signature", "")
    if not signature:
        signature = request.headers.get("X-Razorpay-Signature", "")

    async with AsyncSessionLocal() as session:
        await set_tenant_context(session, str(resolved_tenant_id))
        try:
            service = SaaSBillingService(session)
            await service.process_webhook(
                provider=resolved_provider,
                payload=payload_bytes,
                signature=signature,
                tenant_id=resolved_tenant_id,
            )
            await session.flush()
        finally:
            await clear_tenant_context(session)
    return ok(
        {
            "accepted": True,
            "provider": resolved_provider.value,
            "processed_at": datetime.now(UTC).isoformat(),
        },
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")
