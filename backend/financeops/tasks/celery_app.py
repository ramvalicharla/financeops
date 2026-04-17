from __future__ import annotations

from celery import Celery
from celery.schedules import crontab
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from financeops.config import settings
from financeops.observability.celery_monitor import get_celery_monitor
from financeops.observability.celery_propagation import connect_celery_correlation_signals
from financeops.observability.celery_monitor import connect_task_failure_signal
from financeops.db.models.users import IamSession
from financeops.db.session import AsyncSessionLocal
from financeops.observability.business_metrics import (
    active_tenants_gauge,
    task_queue_depth_gauge,
)
from financeops.tasks.async_runner import run_async

log = logging.getLogger(__name__)

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
        "dead_letter": {"exchange": "dead_letter", "routing_key": "dead_letter"},
    },
    task_default_queue="normal_q",
    task_default_exchange="normal_q",
    task_default_routing_key="normal",
    task_routes={
        "payment.*": {"queue": "critical_q"},
        "financeops.tasks.*": {"queue": "high_q"},
        "financeops.modules.search.tasks.*": {"queue": "low_q"},
        "financeops.modules.*.tasks.*": {"queue": "normal_q"},
        "metrics.*": {"queue": "low_q"},
        "ops.check_dead_letter_queue": {"queue": "dead_letter"},
    },
    imports=(
        "financeops.tasks.auth_tasks",
        "financeops.tasks.payment_tasks",
        "financeops.modules.scheduled_delivery.tasks",
        "financeops.modules.erp_push.application.push_task",
        "financeops.modules.erp_push.application.webhook_task",
        "financeops.modules.accounting_ingestion.application.ocr_task",
        "financeops.modules.accounting_layer.application.beat_tasks",
        "financeops.modules.auto_trigger.pipeline",
        "financeops.modules.search.tasks",
        "financeops.modules.ai_cfo_layer.tasks",
        "financeops.modules.fixed_assets.tasks",
        "financeops.modules.notifications.tasks",
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
        "ops-check-dead-letter-queue-hourly": {
            "task": "ops.check_dead_letter_queue",
            "schedule": 3600.0,
        },
        "accounting-approval-reminders": {
            "task": "accounting_layer.approval_reminder",
            "schedule": 3600.0,
        },
        "accounting-sla-breach-check": {
            "task": "accounting_layer.sla_breach_check",
            "schedule": 1800.0,
        },
        "accounting-daily-digest": {
            "task": "accounting_layer.daily_digest",
            "schedule": 86400.0,
        },
        "fa-monthly-depreciation": {
            "task": "financeops.modules.fixed_assets.tasks.run_monthly_depreciation_task",
            "schedule": crontab(day_of_month=1, hour=2, minute=0),
        },
    },
    # Result expiry
    result_expires=86400,  # 24 hours
)

connect_task_failure_signal()
connect_celery_correlation_signals()


@celery_app.task(name="metrics.update_queue_depths")
def update_queue_depths() -> None:
    inspect = celery_app.control.inspect()
    reserved = inspect.reserved() if inspect is not None else {}
    reserved = reserved or {}
    queue_names = [
        "critical_q",
        "high_q",
        "normal_q",
        "low_q",
        "dead_letter",
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

    run_async(_run())


@celery_app.task(name="ops.check_dead_letter_queue")
def check_dead_letter_queue() -> dict[str, int]:
    stale_count = 0
    total = 0
    cutoff = datetime.now(UTC) - timedelta(hours=24)
    for item in get_celery_monitor().list_dead_letter_items():
        total += 1
        failed_at_raw = item.get("failed_at")
        if not isinstance(failed_at_raw, str):
            continue
        try:
            failed_at = datetime.fromisoformat(failed_at_raw)
        except ValueError:
            continue
        if failed_at.tzinfo is None:
            failed_at = failed_at.replace(tzinfo=UTC)
        if failed_at <= cutoff:
            stale_count += 1
            log.error(
                "dead_letter_item_stale",
                extra={
                    "task_name": item.get("task_name"),
                    "task_id": item.get("task_id"),
                    "error": item.get("error"),
                    "failed_at": failed_at.isoformat(),
                },
            )
    return {"dead_letter_items": total, "stale_items": stale_count}
