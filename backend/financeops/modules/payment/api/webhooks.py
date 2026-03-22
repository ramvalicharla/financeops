from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session
from financeops.config import settings
from financeops.modules.payment.application.webhook_service import WebhookService
from financeops.modules.payment.domain.enums import PaymentProvider
from financeops.shared_kernel.response import ok

router = APIRouter()


def _extract_tenant_id(provider: PaymentProvider, payload: dict[str, Any]) -> uuid.UUID | None:
    try:
        if provider == PaymentProvider.STRIPE:
            metadata = payload.get("data", {}).get("object", {}).get("metadata", {})
            tenant_raw = metadata.get("tenant_id")
        else:
            tenant_raw = payload.get("payload", {}).get("payment", {}).get("entity", {}).get("notes", {}).get("tenant_id")
            if not tenant_raw:
                tenant_raw = payload.get("payload", {}).get("subscription", {}).get("entity", {}).get("notes", {}).get(
                    "tenant_id"
                )
        if not tenant_raw:
            return None
        return uuid.UUID(str(tenant_raw))
    except Exception:
        return None


@router.post("/webhooks/stripe")
async def stripe_webhook(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    payload_bytes = await request.body()
    signature = request.headers.get("Stripe-Signature", "")
    payload = json.loads(payload_bytes.decode("utf-8")) if payload_bytes else {}
    tenant_id = _extract_tenant_id(PaymentProvider.STRIPE, payload)
    if tenant_id is None:
        return ok(
            {"accepted": False, "reason": "tenant_not_resolved"},
            request_id=getattr(request.state, "request_id", None),
        ).model_dump(mode="json")
    try:
        service = WebhookService(session)
        await service.handle_webhook(
            provider=PaymentProvider.STRIPE,
            payload=payload_bytes,
            signature=signature,
            secret=settings.STRIPE_SECRET_KEY,
            tenant_id=tenant_id,
        )
        await session.flush()
    except Exception as exc:
        await session.rollback()
        return ok(
            {"accepted": True, "processed": False, "error": str(exc)},
            request_id=getattr(request.state, "request_id", None),
        ).model_dump(mode="json")
    return ok(
        {"accepted": True, "processed": True},
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.post("/webhooks/razorpay")
async def razorpay_webhook(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    payload_bytes = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")
    payload = json.loads(payload_bytes.decode("utf-8")) if payload_bytes else {}
    tenant_id = _extract_tenant_id(PaymentProvider.RAZORPAY, payload)
    if tenant_id is None:
        return ok(
            {"accepted": False, "reason": "tenant_not_resolved"},
            request_id=getattr(request.state, "request_id", None),
        ).model_dump(mode="json")
    try:
        service = WebhookService(session)
        await service.handle_webhook(
            provider=PaymentProvider.RAZORPAY,
            payload=payload_bytes,
            signature=signature,
            secret=settings.RAZORPAY_KEY_SECRET,
            tenant_id=tenant_id,
        )
        await session.flush()
    except Exception as exc:
        await session.rollback()
        return ok(
            {"accepted": True, "processed": False, "error": str(exc)},
            request_id=getattr(request.state, "request_id", None),
        ).model_dump(mode="json")
    return ok(
        {"accepted": True, "processed": True},
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")
