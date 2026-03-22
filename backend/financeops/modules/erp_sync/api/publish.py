from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user
from financeops.db.models.erp_sync import ExternalSyncPublishEvent
from financeops.db.models.users import IamUser
from financeops.modules.erp_sync.application.publish_service import PublishService
from financeops.shared_kernel.idempotency import require_erp_sync_idempotency_key
from financeops.shared_kernel.response import ok

router = APIRouter()


@router.get("/publish-events")
async def list_publish_events(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    rows = (
        await session.execute(
            select(ExternalSyncPublishEvent)
            .where(ExternalSyncPublishEvent.tenant_id == user.tenant_id)
            .order_by(ExternalSyncPublishEvent.created_at.desc(), ExternalSyncPublishEvent.id.desc())
        )
    ).scalars().all()
    return ok(
        {
            "items": [
                {
                    "id": str(row.id),
                    "sync_run_id": str(row.sync_run_id),
                    "event_status": row.event_status,
                    "idempotency_key": row.idempotency_key,
                    "approved_at": row.approved_at.isoformat() if row.approved_at else None,
                }
                for row in rows
            ]
        },
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.get("/publish-events/{id}")
async def get_publish_event(
    request: Request,
    id: str,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    row = (
        await session.execute(
            select(ExternalSyncPublishEvent).where(
                ExternalSyncPublishEvent.tenant_id == user.tenant_id,
                ExternalSyncPublishEvent.id == uuid.UUID(id),
            )
        )
    ).scalar_one()
    return ok(
        {
            "id": str(row.id),
            "sync_run_id": str(row.sync_run_id),
            "event_status": row.event_status,
            "idempotency_key": row.idempotency_key,
            "approved_by": str(row.approved_by) if row.approved_by else None,
            "approved_at": row.approved_at.isoformat() if row.approved_at else None,
            "rejection_reason": row.rejection_reason,
        },
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.post("/publish-events/{id}/approve")
async def approve_publish_event(
    request: Request,
    id: str,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
    idempotency_key: str = Depends(require_erp_sync_idempotency_key),
) -> dict[str, Any]:
    service = PublishService(session)
    result = await service.approve_publish_event(
        tenant_id=user.tenant_id,
        sync_run_id=uuid.UUID(id),
        idempotency_key=idempotency_key,
        actor_user_id=user.id,
    )
    await session.flush()
    return ok(result, request_id=getattr(request.state, "request_id", None)).model_dump(mode="json")


@router.post("/publish-events/{id}/reject")
async def reject_publish_event(
    request: Request,
    id: str,
    body: dict[str, Any] | None = None,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    payload = body or {}
    service = PublishService(session)
    result = await service.reject_publish_event(
        tenant_id=user.tenant_id,
        sync_run_id=uuid.UUID(id),
        idempotency_key=str(payload.get("idempotency_key", f"reject:{id}")),
        actor_user_id=user.id,
        reason=str(payload.get("reason", "rejected")),
    )
    await session.flush()
    return ok(result, request_id=getattr(request.state, "request_id", None)).model_dump(mode="json")
