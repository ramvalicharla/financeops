from __future__ import annotations

import asyncio
import json
import time
import uuid
from datetime import time
from decimal import Decimal

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import StreamingResponse

from financeops.api.deps import get_async_session, get_current_user, get_redis
from financeops.db.models.users import IamUser
from financeops.modules.notifications.models import NotificationEvent, NotificationPreferences, NotificationReadState
from financeops.modules.notifications.service import (
    get_or_create_preferences,
    list_notifications,
    mark_all_as_read,
    mark_as_read,
    update_preferences,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])
MAX_NOTIFICATION_STREAM_SECONDS = 300.0


class MarkReadRequest(BaseModel):
    notification_ids: list[uuid.UUID] = Field(default_factory=list)


class PreferencesPatchRequest(BaseModel):
    email_enabled: bool | None = None
    inapp_enabled: bool | None = None
    push_enabled: bool | None = None
    quiet_hours_start: time | None = None
    quiet_hours_end: time | None = None
    timezone: str | None = None
    type_preferences: dict | None = None


def _serialize_event(event: NotificationEvent, state: NotificationReadState) -> dict:
    return {
        "id": str(event.id),
        "notification_type": event.notification_type,
        "title": event.title,
        "body": event.body,
        "action_url": event.action_url,
        "metadata": event.metadata_json,
        "channels_sent": list(state.channels_sent or []),
        "created_at": event.created_at.isoformat(),
        "read_state": {
            "is_read": state.is_read,
            "read_at": state.read_at.isoformat() if state.read_at else None,
            "is_dismissed": state.is_dismissed,
            "dismissed_at": state.dismissed_at.isoformat() if state.dismissed_at else None,
            "updated_at": state.updated_at.isoformat(),
        },
    }


def _serialize_preferences(row: NotificationPreferences) -> dict:
    return {
        "id": str(row.id),
        "tenant_id": str(row.tenant_id),
        "user_id": str(row.user_id),
        "email_enabled": row.email_enabled,
        "inapp_enabled": row.inapp_enabled,
        "push_enabled": row.push_enabled,
        "quiet_hours_start": row.quiet_hours_start.isoformat() if row.quiet_hours_start else None,
        "quiet_hours_end": row.quiet_hours_end.isoformat() if row.quiet_hours_end else None,
        "timezone": row.timezone,
        "type_preferences": row.type_preferences or {},
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


@router.get("")
async def list_notifications_endpoint(
    is_read: bool | None = Query(default=None),
    type: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    payload = await list_notifications(
        session,
        tenant_id=user.tenant_id,
        user_id=user.id,
        is_read=is_read,
        notification_type=type,
        limit=limit,
        offset=offset,
    )
    return {
        "unread_count": payload["unread_count"],
        "notifications": [_serialize_event(event, state) for event, state in payload["rows"]],
        "total": payload["total"],
        "limit": limit,
        "offset": offset,
    }


@router.get("/{notification_id}/status")
async def notification_status_endpoint(
    notification_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    row = (
        await session.execute(
            select(NotificationEvent, NotificationReadState)
            .outerjoin(
                NotificationReadState,
                NotificationReadState.notification_event_id == NotificationEvent.id,
            )
            .where(
                NotificationEvent.id == notification_id,
                NotificationEvent.tenant_id == user.tenant_id,
                NotificationEvent.recipient_user_id == user.id,
            )
        )
    ).first()
    if row is None:
        return {"status": "not_found", "notification_id": str(notification_id), "channels_sent": []}
    _, state = row
    channels_sent = list(state.channels_sent or []) if state is not None else []
    return {
        "status": "delivered" if channels_sent else "queued",
        "notification_id": str(notification_id),
        "channels_sent": channels_sent,
    }


@router.post("/read")
async def mark_as_read_endpoint(
    body: MarkReadRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    updated = await mark_as_read(
        session,
        tenant_id=user.tenant_id,
        user_id=user.id,
        notification_ids=body.notification_ids,
    )
    return {"updated": updated}


@router.post("/read-all")
async def mark_all_as_read_endpoint(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    updated = await mark_all_as_read(session, tenant_id=user.tenant_id, user_id=user.id)
    return {"updated": updated}


@router.get("/unread-count")
async def unread_count_endpoint(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    payload = await list_notifications(
        session,
        tenant_id=user.tenant_id,
        user_id=user.id,
        is_read=False,
        limit=1,
        offset=0,
    )
    return {"count": int(payload["total"])}


@router.get("/preferences")
async def get_preferences_endpoint(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    row = await get_or_create_preferences(session, tenant_id=user.tenant_id, user_id=user.id)
    return _serialize_preferences(row)


@router.patch("/preferences")
async def update_preferences_endpoint(
    body: PreferencesPatchRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    updates = body.model_dump(exclude_none=True)
    row = await update_preferences(
        session,
        tenant_id=user.tenant_id,
        user_id=user.id,
        updates=updates,
    )
    return _serialize_preferences(row)


@router.get("/stream")
async def stream_notifications_endpoint(
    redis_client: aioredis.Redis = Depends(get_redis),
    user: IamUser = Depends(get_current_user),
) -> StreamingResponse:
    channel = f"notifications:{user.tenant_id}:{user.id}"
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(channel)

    async def _event_stream():
        started_at = time.monotonic()
        try:
            yield "event: ready\ndata: {}\n\n"
            while True:
                if time.monotonic() - started_at >= MAX_NOTIFICATION_STREAM_SECONDS:
                    yield "event: timeout\ndata: {}\n\n"
                    break
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=5.0)
                if message and message.get("type") == "message":
                    payload = message.get("data")
                    if isinstance(payload, (dict, list)):
                        data = json.dumps(payload)
                    else:
                        data = str(payload)
                    yield f"data: {data}\n\n"
                else:
                    yield "event: ping\ndata: {}\n\n"
                await asyncio.sleep(0.25)
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()

    return StreamingResponse(_event_stream(), media_type="text/event-stream")


__all__ = ["router"]
