from __future__ import annotations

import asyncio
import uuid
from typing import Any

from celery import Task

from financeops.db.session import tenant_session
from financeops.modules.erp_push.application.webhook_processor import (
    process_webhook_event,
)
from financeops.tasks.base_task import FinanceOpsTask
from financeops.tasks.celery_app import celery_app


@celery_app.task(
    bind=True,
    base=FinanceOpsTask,
    max_retries=3,
    queue="normal_q",
    name="erp_push.process_webhook_event",
)
def process_webhook_event_task(
    self: Task,
    event_id: str,
    tenant_id: str,
    canonical_event_type: str,
) -> dict[str, Any]:
    async def _run() -> dict[str, Any]:
        async with tenant_session(tenant_id) as db:
            return await process_webhook_event(
                db,
                event_id=uuid.UUID(event_id),
                tenant_id=uuid.UUID(tenant_id),
                canonical_event_type=canonical_event_type,
            )

    try:
        return asyncio.run(_run())
    except Exception as exc:
        raise self.retry(exc=exc, countdown=30 * (2**self.request.retries))
