from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.users import IamUser
from financeops.modules.notifications.channels.email_channel import send_email
from financeops.modules.notifications.channels.inapp_channel import send_inapp
from financeops.modules.notifications.channels.push_channel import send_push
from financeops.modules.notifications.models import (
    NotificationEvent,
    NotificationPreferences,
    NotificationReadState,
)
from financeops.modules.white_label.models import WhiteLabelConfig

log = logging.getLogger(__name__)


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _in_quiet_hours(
    now_utc: datetime,
    timezone_name: str,
    quiet_start: time | None,
    quiet_end: time | None,
) -> bool:
    if quiet_start is None or quiet_end is None:
        return False
    try:
        now_local = now_utc.astimezone(ZoneInfo(timezone_name))
    except Exception:
        now_local = now_utc
    now_time = now_local.timetz().replace(tzinfo=None)

    if quiet_start <= quiet_end:
        return quiet_start <= now_time < quiet_end
    return now_time >= quiet_start or now_time < quiet_end


def _channel_allowed_for_type(
    preferences: NotificationPreferences,
    notification_type: str,
    channel: str,
) -> bool:
    raw = preferences.type_preferences or {}
    if not isinstance(raw, dict):
        return True
    per_type = raw.get(notification_type, {})
    if not isinstance(per_type, dict):
        return True
    override_value = per_type.get(channel)
    if override_value is None:
        return True
    return bool(override_value)


async def get_or_create_preferences(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
) -> NotificationPreferences:
    row = (
        await session.execute(
            select(NotificationPreferences).where(
                NotificationPreferences.tenant_id == tenant_id,
                NotificationPreferences.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if row is not None:
        return row

    row = NotificationPreferences(
        tenant_id=tenant_id,
        user_id=user_id,
        email_enabled=True,
        inapp_enabled=True,
        push_enabled=False,
        timezone="Asia/Kolkata",
        type_preferences={},
    )
    session.add(row)
    await session.flush()
    return row


async def update_preferences(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    updates: dict,
) -> NotificationPreferences:
    row = await get_or_create_preferences(session, tenant_id, user_id)
    allowed = {
        "email_enabled",
        "inapp_enabled",
        "push_enabled",
        "quiet_hours_start",
        "quiet_hours_end",
        "timezone",
        "type_preferences",
    }
    for key, value in updates.items():
        if key in allowed:
            setattr(row, key, value)
    row.updated_at = _now_utc()
    await session.flush()
    return row


async def send_notification(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    recipient_user_id: uuid.UUID,
    notification_type: str,
    title: str,
    body: str,
    action_url: str | None = None,
    metadata: dict | None = None,
) -> NotificationEvent:
    """
    Core notification dispatcher. Channel failures are logged and skipped.
    """
    preferences = await get_or_create_preferences(session, tenant_id, recipient_user_id)
    recipient = (
        await session.execute(
            select(IamUser).where(
                IamUser.id == recipient_user_id,
                IamUser.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()

    now = _now_utc()
    in_quiet = _in_quiet_hours(
        now,
        str(preferences.timezone or "Asia/Kolkata"),
        preferences.quiet_hours_start,
        preferences.quiet_hours_end,
    )

    email_allowed = (
        bool(preferences.email_enabled)
        and not in_quiet
        and _channel_allowed_for_type(preferences, notification_type, "email")
    )
    # In-app is always created for bell history; allow opt-out only via explicit type override.
    inapp_allowed = _channel_allowed_for_type(preferences, notification_type, "inapp")
    push_allowed = (
        bool(preferences.push_enabled)
        and _channel_allowed_for_type(preferences, notification_type, "push")
    )

    channels_sent: list[str] = []
    if inapp_allowed:
        channels_sent.append("inapp")
    if email_allowed:
        channels_sent.append("email")
    if push_allowed:
        channels_sent.append("push")

    event = NotificationEvent(
        tenant_id=tenant_id,
        recipient_user_id=recipient_user_id,
        notification_type=notification_type,
        title=title,
        body=body,
        action_url=action_url,
        metadata_json=metadata or {},
        channels_sent=channels_sent,
    )
    session.add(event)
    await session.flush()

    if inapp_allowed:
        try:
            await send_inapp(session, event)
        except Exception as exc:  # noqa: BLE001
            log.warning("notification_inapp_failed event=%s error=%s", event.id, exc)

    if email_allowed and recipient is not None and recipient.email:
        try:
            brand = (
                await session.execute(
                    select(WhiteLabelConfig.brand_name).where(
                        WhiteLabelConfig.tenant_id == tenant_id
                    )
                )
            ).scalar_one_or_none()
            await send_email(event, recipient.email, brand_name=brand)
        except Exception as exc:  # noqa: BLE001
            log.warning("notification_email_failed event=%s error=%s", event.id, exc)

    if push_allowed:
        try:
            # Sprint 10: token registry not present yet; use metadata token if supplied.
            fcm_token = str((metadata or {}).get("fcm_token", ""))
            await send_push(event, fcm_token)
        except Exception as exc:  # noqa: BLE001
            log.warning("notification_push_failed event=%s error=%s", event.id, exc)

    return event


async def get_unread_notifications(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    stmt = (
        select(NotificationEvent, NotificationReadState)
        .join(
            NotificationReadState,
            NotificationReadState.notification_event_id == NotificationEvent.id,
        )
        .where(
            NotificationEvent.tenant_id == tenant_id,
            NotificationReadState.user_id == user_id,
            NotificationReadState.is_read.is_(False),
        )
    )
    total = int(
        (
            await session.execute(
                select(func.count()).select_from(stmt.subquery())
            )
        ).scalar_one()
    )
    rows = (
        await session.execute(
            stmt.order_by(desc(NotificationEvent.created_at), desc(NotificationEvent.id))
            .limit(limit)
            .offset(offset)
        )
    ).all()
    return {
        "unread_count": total,
        "notifications": rows,
        "total": total,
    }


async def mark_as_read(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    notification_ids: list[uuid.UUID],
) -> int:
    if not notification_ids:
        return 0
    rows = (
        await session.execute(
            select(NotificationReadState)
            .join(
                NotificationEvent,
                NotificationEvent.id == NotificationReadState.notification_event_id,
            )
            .where(
                NotificationReadState.user_id == user_id,
                NotificationReadState.tenant_id == tenant_id,
                NotificationEvent.id.in_(notification_ids),
            )
        )
    ).scalars().all()
    now = _now_utc()
    updated = 0
    for row in rows:
        if not row.is_read:
            row.is_read = True
            row.read_at = now
            row.updated_at = now
            updated += 1
    await session.flush()
    return updated


async def mark_all_as_read(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
) -> int:
    rows = (
        await session.execute(
            select(NotificationReadState).where(
                NotificationReadState.tenant_id == tenant_id,
                NotificationReadState.user_id == user_id,
                NotificationReadState.is_read.is_(False),
            )
        )
    ).scalars().all()
    now = _now_utc()
    for row in rows:
        row.is_read = True
        row.read_at = now
        row.updated_at = now
    await session.flush()
    return len(rows)


async def list_notifications(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    is_read: bool | None = None,
    notification_type: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    stmt = (
        select(NotificationEvent, NotificationReadState)
        .join(
            NotificationReadState,
            and_(
                NotificationReadState.notification_event_id == NotificationEvent.id,
                NotificationReadState.user_id == user_id,
                NotificationReadState.tenant_id == tenant_id,
            ),
        )
        .where(NotificationEvent.tenant_id == tenant_id)
    )
    if is_read is not None:
        stmt = stmt.where(NotificationReadState.is_read.is_(is_read))
    if notification_type:
        stmt = stmt.where(NotificationEvent.notification_type == notification_type)

    total = int(
        (
            await session.execute(
                select(func.count()).select_from(stmt.subquery())
            )
        ).scalar_one()
    )
    rows = (
        await session.execute(
            stmt.order_by(desc(NotificationEvent.created_at), desc(NotificationEvent.id))
            .limit(limit)
            .offset(offset)
        )
    ).all()

    unread_count = int(
        (
            await session.execute(
                select(func.count())
                .select_from(NotificationReadState)
                .where(
                    NotificationReadState.tenant_id == tenant_id,
                    NotificationReadState.user_id == user_id,
                    NotificationReadState.is_read.is_(False),
                )
            )
        ).scalar_one()
    )
    return {"rows": rows, "total": total, "unread_count": unread_count}


__all__ = [
    "get_or_create_preferences",
    "get_unread_notifications",
    "list_notifications",
    "mark_all_as_read",
    "mark_as_read",
    "send_notification",
    "update_preferences",
]

