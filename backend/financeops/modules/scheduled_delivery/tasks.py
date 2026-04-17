from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

import sentry_sdk
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError, InterfaceError, OperationalError

from financeops.db.models.tenants import IamTenant, TenantStatus
from financeops.db.session import AsyncSessionLocal, clear_tenant_context, set_tenant_context
from financeops.modules.scheduled_delivery.application.delivery_service import (
    DeliveryConfigurationError,
    DeliveryService,
    normalize_delivery_idempotency_key,
)
from financeops.modules.scheduled_delivery.domain.enums import DeliveryStatus
from financeops.modules.scheduled_delivery.infrastructure.repository import (
    DeliveryRepository,
)
from financeops.tasks.async_runner import run_async
from financeops.tasks.celery_app import celery_app

log = logging.getLogger(__name__)


async def _deliver_schedule_once(
    schedule_id: str | uuid.UUID,
    tenant_id: str | uuid.UUID,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    parsed_schedule_id = uuid.UUID(str(schedule_id))
    parsed_tenant_id = uuid.UUID(str(tenant_id))
    resolved_idempotency_key = normalize_delivery_idempotency_key(idempotency_key)
    service = DeliveryService()
    repository = DeliveryRepository()
    async with AsyncSessionLocal() as session:
        try:
            await set_tenant_context(session, str(parsed_tenant_id))
            if resolved_idempotency_key:
                existing = await repository.get_delivered_log_by_idempotency_key(
                    db=session,
                    tenant_id=parsed_tenant_id,
                    schedule_id=parsed_schedule_id,
                    idempotency_key=resolved_idempotency_key,
                )
                if existing is not None:
                    log.info("Already delivered: %s. Skipping.", resolved_idempotency_key)
                    return {
                        "schedule_id": str(parsed_schedule_id),
                        "status": DeliveryStatus.DELIVERED.value,
                        "duplicate": True,
                        "log_ids": [str(existing.id)],
                    }

            logs = await service.trigger_schedule(
                db=session,
                schedule_id=parsed_schedule_id,
                tenant_id=parsed_tenant_id,
                idempotency_key=resolved_idempotency_key,
            )
            await session.flush()
            await session.commit()
            return {
                "schedule_id": str(parsed_schedule_id),
                "status": DeliveryStatus.DELIVERED.value,
                "duplicate": False,
                "log_ids": [str(row.id) for row in logs],
            }
        except Exception:
            await session.rollback()
            raise
        finally:
            await clear_tenant_context(session)


@celery_app.task(
    name="scheduled_delivery.deliver",
    bind=True,
    max_retries=3,
    default_retry_delay=300,
    acks_late=True,
    queue="critical_q",
)
def deliver_schedule_task(
    self,
    schedule_id: str,
    tenant_id: str,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    try:
        return run_async(
            _deliver_schedule_once(
                schedule_id=schedule_id,
                tenant_id=tenant_id,
                idempotency_key=idempotency_key,
            )
        )
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
                        resolved_key = (
                            f"scheduled:{schedule.id}:{schedule.next_run_at.astimezone(UTC).isoformat()}"
                            if schedule.next_run_at is not None
                            else f"scheduled:{schedule.id}:{datetime.now(UTC).isoformat()}"
                        )
                        deliver_schedule_task.delay(
                            str(schedule.id),
                            str(tenant_id),
                            resolved_key,
                        )
                        enqueued += 1
                finally:
                    await clear_tenant_context(session)
        return {"scheduled": enqueued}

    return run_async(_run())


__all__ = ["_deliver_schedule_once", "deliver_schedule_task", "poll_due_schedules_task"]
