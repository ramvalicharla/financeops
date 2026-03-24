from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.config import settings
from financeops.modules.notifications.models import NotificationEvent, NotificationReadState

log = logging.getLogger(__name__)
_redis_client: aioredis.Redis | None = None


async def _get_redis_client() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            str(settings.REDIS_URL),
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_client


async def send_inapp(
    session: AsyncSession,
    notification_event: NotificationEvent,
) -> bool:
    """
    Create mutable in-app read state and publish a realtime payload.
    """
    row = NotificationReadState(
        notification_event_id=notification_event.id,
        tenant_id=notification_event.tenant_id,
        user_id=notification_event.recipient_user_id,
        is_read=False,
        is_dismissed=False,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.add(row)
    await session.flush()

    payload = {
        "id": str(notification_event.id),
        "type": notification_event.notification_type,
        "title": notification_event.title,
        "body": notification_event.body,
        "action_url": notification_event.action_url,
        "created_at": notification_event.created_at.isoformat(),
    }
    channel = (
        f"notifications:{notification_event.tenant_id}:{notification_event.recipient_user_id}"
    )
    try:
        redis_client = await _get_redis_client()
        await redis_client.publish(channel, json.dumps(payload))
    except Exception as exc:  # noqa: BLE001
        log.warning("notification_inapp_pubsub_failed event=%s error=%s", notification_event.id, exc)
    return True


__all__ = ["send_inapp"]

