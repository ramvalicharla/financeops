from __future__ import annotations

import uuid
from typing import Any

import sentry_sdk
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError, InterfaceError, OperationalError

from financeops.db.models.tenants import IamTenant, TenantStatus
from financeops.db.session import AsyncSessionLocal, clear_tenant_context, set_tenant_context
from financeops.modules.scheduled_delivery.application.delivery_service import (
    DeliveryConfigurationError,
    DeliveryService,
)
from financeops.modules.scheduled_delivery.infrastructure.repository import (
    DeliveryRepository,
)
from financeops.tasks.async_runner import run_async
from financeops.tasks.celery_app import celery_app


@celery_app.task(
    name="scheduled_delivery.deliver",
    bind=True,
    max_retries=3,
    default_retry_delay=300,
    acks_late=True,
)
def deliver_schedule_task(
    self,
    schedule_id: str,
    tenant_id: str,
) -> dict[str, Any]:
    async def _run() -> dict[str, Any]:
        parsed_schedule_id = uuid.UUID(str(schedule_id))
        parsed_tenant_id = uuid.UUID(str(tenant_id))
        service = DeliveryService()
        async with AsyncSessionLocal() as session:
            try:
                await set_tenant_context(session, str(parsed_tenant_id))
                logs = await service.trigger_schedule(
                    db=session,
                    schedule_id=parsed_schedule_id,
                    tenant_id=parsed_tenant_id,
                )
                await session.flush()
                return {
                    "schedule_id": str(parsed_schedule_id),
                    "status": "DELIVERED",
                    "log_ids": [str(row.id) for row in logs],
                }
            finally:
                await clear_tenant_context(session)

    try:
        return run_async(_run())
    except (DeliveryConfigurationError, ValueError):
        raise
    except (OperationalError, InterfaceError, DBAPIError, ConnectionError, TimeoutError, OSError) as exc:
        raise self.retry(exc=exc)
    except Exception as exc:
        sentry_sdk.capture_exception(exc)
        raise


@celery_app.task(name="scheduled_delivery.poll_due")
def poll_due_schedules_task() -> dict[str, int]:
    async def _run() -> dict[str, int]:
        repository = DeliveryRepository()
        enqueued = 0
        async with AsyncSessionLocal() as session:
            tenant_ids = list(
                (
                    await session.execute(
                        select(IamTenant.id).where(IamTenant.status == TenantStatus.active)
                    )
                ).scalars()
            )
            for tenant_id in tenant_ids:
                try:
                    await set_tenant_context(session, str(tenant_id))
                    due_schedules = await repository.list_due_schedules(
                        db=session,
                        tenant_id=tenant_id,
                    )
                    for schedule in due_schedules:
                        deliver_schedule_task.delay(str(schedule.id), str(tenant_id))
                        enqueued += 1
                finally:
                    await clear_tenant_context(session)
        return {"scheduled": enqueued}

    return run_async(_run())


__all__ = ["deliver_schedule_task", "poll_due_schedules_task"]
