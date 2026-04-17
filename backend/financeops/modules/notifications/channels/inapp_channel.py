from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.config import settings
from financeops.modules.notifications.models import NotificationEvent, NotificationReadState

log = logging.getLogger(__name__)


def _append_channel(channels: list[str] | None, channel: str) -> list[str]:
    existing = [str(item) for item in (channels or [])]
    if channel not in existing:
        existing.append(channel)
    return existing


async def send_inapp(
    session: AsyncSession,
    notification_event: NotificationEvent,
) -> bool:
    """
    Create mutable in-app read state and publish a realtime payload.
    """
    row = (
        await session.execute(
            select(NotificationReadState).where(
                NotificationReadState.notification_event_id == notification_event.id
            )
        )
    ).scalar_one_or_none()
    if row is None:
        row = NotificationReadState(
            notification_event_id=notification_event.id,
            tenant_id=notification_event.tenant_id,
            user_id=notification_event.recipient_user_id,
            is_read=False,
            is_dismissed=False,
            channels_sent=["inapp"],
            delivery_status="delivered",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        session.add(row)
    else:
        row.channels_sent = _append_channel(row.channels_sent, "inapp")
        row.delivery_status = "delivered"
        row.updated_at = datetime.now(UTC)
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
        # Avoid keeping a module-global async Redis client across app/test loops.
        redis_client = aioredis.from_url(
            str(settings.REDIS_URL),
            encoding="utf-8",
            decode_responses=True,
        )
        try:
            await redis_client.publish(channel, json.dumps(payload))
        finally:
            await redis_client.aclose()
    except Exception as exc:  # noqa: BLE001
        log.warning("notification_inapp_pubsub_failed event=%s error=%s", notification_event.id, exc)
    return True


__all__ = ["send_inapp"]
