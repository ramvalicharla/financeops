from __future__ import annotations

from celery import Celery
import asyncio

from sqlalchemy import func, select

from financeops.config import settings
from financeops.observability.celery_monitor import connect_task_failure_signal
from financeops.db.models.users import IamSession
from financeops.db.session import AsyncSessionLocal
from financeops.observability.business_metrics import (
    active_tenants_gauge,
    task_queue_depth_gauge,
)

celery_app = Celery("financeops")

celery_app.conf.update(
    # Broker and result backend
    broker_url=str(settings.REDIS_URL),
    result_backend=str(settings.REDIS_URL),
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    # Timezone
    timezone="UTC",
    enable_utc=True,
    # Reliability settings (critical for financial tasks)
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_reject_on_worker_lost=True,
    worker_concurrency=4,
    worker_max_tasks_per_child=1000,
    task_soft_time_limit=300,
    task_time_limit=600,
    # Retry settings
    task_max_retries=3,
    task_default_retry_delay=60,  # seconds; tasks use exponential backoff
    # Queue definitions
    task_queues={
        "critical_q": {"exchange": "critical_q", "routing_key": "critical"},
        "high_q": {"exchange": "high_q", "routing_key": "high"},
        "normal_q": {"exchange": "normal_q", "routing_key": "normal"},
        "low_q": {"exchange": "low_q", "routing_key": "low"},
    },
    task_default_queue="normal_q",
    task_default_exchange="normal_q",
    task_default_routing_key="normal",
    task_routes={
        "financeops.tasks.*": {"queue": "default"},
        "financeops.modules.search.tasks.*": {"queue": "search"},
        "financeops.modules.*.tasks.*": {"queue": "finance"},
    },
    imports=(
        "financeops.tasks.payment_tasks",
        "financeops.modules.scheduled_delivery.tasks",
        "financeops.modules.auto_trigger.pipeline",
        "financeops.modules.search.tasks",
    ),
    beat_schedule={
        "payment-check-trial-conversions-daily-0000-utc": {
            "task": "payment.check_trial_conversions",
            "schedule": 86400.0,
        },
        "payment-check-grace-periods-every-6h": {
            "task": "payment.check_grace_periods",
            "schedule": 21600.0,
        },
        "payment-retry-failed-payments-daily-0600-utc": {
            "task": "payment.retry_failed_payments",
            "schedule": 86400.0,
        },
        "payment-expire-credits-daily-2300-utc": {
            "task": "payment.expire_credits",
            "schedule": 86400.0,
        },
        "scheduled-delivery-poll-due-every-minute": {
            "task": "scheduled_delivery.poll_due",
            "schedule": 60.0,
        },
        "metrics-update-queue-depths-every-30s": {
            "task": "metrics.update_queue_depths",
            "schedule": 30.0,
        },
        "metrics-update-active-tenants-every-5m": {
            "task": "metrics.update_active_tenants",
            "schedule": 300.0,
        },
    },
    # Result expiry
    result_expires=86400,  # 24 hours
)

connect_task_failure_signal()


@celery_app.task(name="metrics.update_queue_depths")
def update_queue_depths() -> None:
    inspect = celery_app.control.inspect()
    reserved = inspect.reserved() if inspect is not None else {}
    reserved = reserved or {}
    queue_names = [
        "file_scan",
        "parse",
        "erp_sync",
        "report_gen",
        "email",
        "ai_inference",
        "notification",
    ]
    depth_total = sum(len(tasks) for tasks in reserved.values() if isinstance(tasks, list))
    for queue_name in queue_names:
        task_queue_depth_gauge.labels(queue_name=queue_name).set(depth_total)


@celery_app.task(name="metrics.update_active_tenants")
def update_active_tenants() -> None:
    async def _run() -> None:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(func.count(func.distinct(IamSession.tenant_id))).where(
                    IamSession.revoked_at.is_(None)
                )
            )
            count = int(result.scalar_one() or 0)
            active_tenants_gauge.set(count)

    asyncio.run(_run())
