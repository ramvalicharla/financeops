from __future__ import annotations

import logging
import uuid
from typing import Any

from celery import Task
from sqlalchemy import select

from financeops.db.session import tenant_session
from financeops.modules.notifications.models import NotificationReadState
from financeops.modules.notifications.service import deliver_notification_event
from financeops.tasks.async_runner import run_async
from financeops.tasks.base_task import FinanceOpsTask
from financeops.tasks.celery_app import celery_app

log = logging.getLogger(__name__)


def schedule_notification_delivery(
    *,
    notification_event_id: uuid.UUID,
    tenant_id: uuid.UUID,
):
    try:
        return send_notification_task.delay(str(notification_event_id), str(tenant_id))
    except Exception as exc:
        log.warning(
            "task_enqueue_failed task=%s error=%s",
            send_notification_task.name,
            exc,
        )


async def run_notification_delivery(
    *,
    notification_event_id: str,
    tenant_id: str,
) -> dict[str, Any]:
    async with tenant_session(tenant_id) as session:
        event = await deliver_notification_event(
            session,
            tenant_id=uuid.UUID(str(tenant_id)),
            notification_event_id=uuid.UUID(str(notification_event_id)),
        )
        if event is None:
            return {
                "notification_event_id": notification_event_id,
                "status": "missing",
                "channels_sent": [],
            }
        delivery_state = (
            await session.execute(
                select(NotificationReadState).where(
                    NotificationReadState.notification_event_id == event.id
                )
            )
        ).scalar_one_or_none()
        channels_sent = list(delivery_state.channels_sent or []) if delivery_state is not None else []
        return {
            "notification_event_id": str(event.id),
            "status": "complete",
            "channels_sent": channels_sent,
        }


@celery_app.task(
    bind=True,
    base=FinanceOpsTask,
    max_retries=3,
    queue="critical_q",
    name="notifications.send_notification",
)
def send_notification_task(
    self: Task,
    notification_event_id: str,
    tenant_id: str,
) -> dict[str, Any]:
    try:
        return run_async(
            run_notification_delivery(
                notification_event_id=notification_event_id,
                tenant_id=tenant_id,
            )
        )
    except Exception as exc:  # pragma: no cover - celery retry behavior
        log.exception(
            "notification_delivery_task_failed",
            extra={"notification_event_id": notification_event_id, "tenant_id": tenant_id},
        )
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))


__all__ = [
    "run_notification_delivery",
    "schedule_notification_delivery",
    "send_notification_task",
]
