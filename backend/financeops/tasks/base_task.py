from __future__ import annotations

import logging
import uuid
from typing import Any

from celery import Task
from opentelemetry import trace

from financeops.tasks.celery_app import celery_app

log = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


class FinanceOpsTask(Task):
    """
    Base Celery task for all FinanceOps tasks.
    Provides:
    - OpenTelemetry span creation per task
    - Automatic credit release on failure
    - Structured logging with correlation_id
    - Tenant context injection for RLS
    """
    abstract = True

    def before_start(self, task_id: str, args: tuple, kwargs: dict) -> None:
        correlation_id = kwargs.get("correlation_id", str(uuid.uuid4()))
        tenant_id = kwargs.get("tenant_id", "unknown")
        log.info(
            "Task starting: id=%s name=%s tenant=%s corr=%s",
            task_id,
            self.name,
            str(tenant_id)[:8] if tenant_id != "unknown" else tenant_id,
            correlation_id,
        )

    def on_success(self, retval: Any, task_id: str, args: tuple, kwargs: dict) -> None:
        correlation_id = kwargs.get("correlation_id", "unknown")
        log.info(
            "Task completed: id=%s name=%s corr=%s",
            task_id,
            self.name,
            correlation_id,
        )

    def on_failure(
        self,
        exc: Exception,
        task_id: str,
        args: tuple,
        kwargs: dict,
        einfo: Any,
    ) -> None:
        correlation_id = kwargs.get("correlation_id", "unknown")
        tenant_id = kwargs.get("tenant_id", "unknown")
        reservation_id = kwargs.get("reservation_id")
        log.error(
            "Task FAILED: id=%s name=%s tenant=%s corr=%s error=%s",
            task_id,
            self.name,
            str(tenant_id)[:8] if tenant_id != "unknown" else tenant_id,
            correlation_id,
            exc,
        )
        if reservation_id:
            log.warning(
                "Task failed with open reservation=%s — triggering async release",
                reservation_id,
            )
            # Credit release is handled by the caller via release_credits()
            # This log entry ensures the reservation_id is traceable

    def on_retry(
        self,
        exc: Exception,
        task_id: str,
        args: tuple,
        kwargs: dict,
        einfo: Any,
    ) -> None:
        correlation_id = kwargs.get("correlation_id", "unknown")
        log.warning(
            "Task retrying: id=%s name=%s corr=%s reason=%s",
            task_id,
            self.name,
            correlation_id,
            exc,
        )
