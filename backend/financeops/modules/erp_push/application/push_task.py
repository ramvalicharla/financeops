from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from celery import Task

from financeops.db.models.erp_push import PushStatus
from financeops.db.session import tenant_session
from financeops.modules.erp_push.application.posting_service import SoftPushError, execute_push
from financeops.tasks.base_task import FinanceOpsTask
from financeops.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

_MAX_PUSH_RETRIES = 5
_BASE_RETRY_DELAY = 60


@celery_app.task(
    bind=True,
    base=FinanceOpsTask,
    max_retries=_MAX_PUSH_RETRIES,
    queue="high_q",
    name="erp_push.push_journal",
)
def push_journal_task(
    self: Task,
    jv_id: str,
    tenant_id: str,
    connection_id: str,
    connector_type: str,
    simulation: bool = False,
) -> dict[str, Any]:
    async def _run() -> dict[str, Any]:
        async with tenant_session(tenant_id) as db:
            run = await execute_push(
                db,
                jv_id=uuid.UUID(jv_id),
                tenant_id=uuid.UUID(tenant_id),
                connection_id=uuid.UUID(connection_id),
                connector_type=connector_type,
                simulation=simulation,
            )
            return {
                "status": run.status,
                "external_journal_id": run.external_journal_id,
                "error_code": run.error_code,
                "error_message": run.error_message,
                "error_category": run.error_category,
                "attempt_number": run.attempt_number,
            }

    try:
        result = asyncio.run(_run())
    except SoftPushError as exc:
        countdown = _BASE_RETRY_DELAY * (2 ** self.request.retries)
        raise self.retry(exc=exc, countdown=countdown)
    except Exception as exc:
        countdown = _BASE_RETRY_DELAY * (2 ** self.request.retries)
        raise self.retry(exc=exc, countdown=countdown)

    if result.get("status") == PushStatus.DEAD_LETTER:
        push_journal_dead_letter.apply_async(
            kwargs={
                "jv_id": jv_id,
                "connector_type": connector_type,
                "error_code": str(result.get("error_code") or ""),
                "error_message": str(result.get("error_message") or ""),
            },
            queue="low_q",
        )

    return result


@celery_app.task(queue="low_q", name="erp_push.dead_letter")
def push_journal_dead_letter(
    jv_id: str,
    connector_type: str,
    error_code: str,
    error_message: str,
) -> None:
    logger.critical(
        "ERP push dead-lettered",
        extra={
            "jv_id": jv_id,
            "connector_type": connector_type,
            "error_code": error_code,
            "error_message": error_message,
        },
    )


@celery_app.task(
    bind=True,
    base=FinanceOpsTask,
    max_retries=3,
    queue="normal_q",
    name="erp_push.push_attachment",
)
def push_attachment_task(
    self: Task,
    attachment_id: str,
    jv_id: str,
    tenant_id: str,
    connection_id: str,
    connector_type: str,
) -> dict[str, Any]:
    _ = (self, tenant_id, connection_id, connector_type)
    return {"status": "PENDING", "attachment_id": attachment_id, "jv_id": jv_id}
