from __future__ import annotations

import json
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.session import get_async_session
from financeops.modules.erp_push.application.webhook_service import ingest_webhook
from financeops.shared_kernel.response import ok

webhook_router = APIRouter(prefix="/webhooks", tags=["ERP Webhooks"])


async def _get_tenant_from_header(
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
) -> uuid.UUID:
    try:
        return uuid.UUID(x_tenant_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="Invalid X-Tenant-ID header - expected UUID",
        ) from exc


async def _ingest_connector_webhook(
    *,
    request: Request,
    session: AsyncSession,
    tenant_id: uuid.UUID,
    connector_type: str,
    webhook_secret: str | None,
) -> dict[str, Any]:
    raw_body = await request.body()
    headers = {key.lower(): value for key, value in request.headers.items()}

    try:
        payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON payload") from exc

    await ingest_webhook(
        session,
        tenant_id=tenant_id,
        connector_type=connector_type,
        raw_body=raw_body,
        headers=headers,
        payload=payload,
        webhook_secret=webhook_secret,
    )
    await session.commit()
    return ok(
        {"accepted": True, "processed_async": True},
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@webhook_router.post("/zoho")
async def zoho_webhook_endpoint(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    tenant_id: Annotated[uuid.UUID, Depends(_get_tenant_from_header)],
) -> dict[str, Any]:
    headers = {key.lower(): value for key, value in request.headers.items()}
    webhook_secret = headers.get("x-webhook-secret")
    return await _ingest_connector_webhook(
        request=request,
        session=session,
        tenant_id=tenant_id,
        connector_type="ZOHO",
        webhook_secret=webhook_secret,
    )


@webhook_router.post("/qbo")
async def qbo_webhook_endpoint(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    tenant_id: Annotated[uuid.UUID, Depends(_get_tenant_from_header)],
) -> dict[str, Any]:
    headers = {key.lower(): value for key, value in request.headers.items()}
    webhook_secret = headers.get("x-webhook-secret")
    return await _ingest_connector_webhook(
        request=request,
        session=session,
        tenant_id=tenant_id,
        connector_type="QBO",
        webhook_secret=webhook_secret,
    )


@webhook_router.post("/tally")
async def tally_webhook_endpoint(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    tenant_id: Annotated[uuid.UUID, Depends(_get_tenant_from_header)],
) -> dict[str, Any]:
    return await _ingest_connector_webhook(
        request=request,
        session=session,
        tenant_id=tenant_id,
        connector_type="TALLY",
        webhook_secret=None,
    )
