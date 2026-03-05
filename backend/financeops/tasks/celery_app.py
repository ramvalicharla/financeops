from __future__ import annotations

from celery import Celery

from financeops.config import settings

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
    # Result expiry
    result_expires=86400,  # 24 hours
)
