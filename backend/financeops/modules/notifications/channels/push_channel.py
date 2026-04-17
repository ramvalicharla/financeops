from __future__ import annotations

import logging

from financeops.config import settings
from financeops.modules.notifications.models import NotificationEvent

log = logging.getLogger(__name__)


async def send_push(
    notification_event: NotificationEvent,
    fcm_token: str,
) -> bool:
    """
    Push delivery degrades gracefully when no provider is configured.
    """
    if not getattr(settings, "FIREBASE_SERVER_KEY", ""):
        log.warning(
            "Push channel not configured event=%s user=%s token=%s",
            notification_event.id,
            notification_event.recipient_user_id,
            fcm_token[:8] if fcm_token else "none",
        )
        return False

    log.info(
        "push_notification_would_send event=%s user=%s",
        notification_event.id,
        notification_event.recipient_user_id,
    )
    return True


__all__ = ["send_push"]
