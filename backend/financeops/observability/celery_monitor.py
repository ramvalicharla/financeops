from __future__ import annotations

import asyncio
import logging
from functools import lru_cache
from typing import Any

import redis.asyncio as aioredis
import sentry_sdk
from celery.signals import task_failure

from financeops.config import settings

log = logging.getLogger(__name__)


class CeleryMonitor:
    ALERT_THRESHOLD = 100
    CRITICAL_THRESHOLD_MULTIPLIER = 5
    QUEUE_KEYS: dict[str, str] = {
        "default": "celery",
        "financial": "financial",
        "sync": "sync",
        "notifications": "notifications",
    }

    def __init__(self, redis_url: str) -> None:
        self._redis_url = redis_url

    async def get_queue_depths(self) -> dict[str, int]:
        client = aioredis.from_url(
            self._redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
        try:
            tasks = [client.llen(key) for key in self.QUEUE_KEYS.values()]
            results = await asyncio.wait_for(asyncio.gather(*tasks), timeout=1.5)
            return {
                queue_name: int(results[index])
                for index, queue_name in enumerate(self.QUEUE_KEYS.keys())
            }
        except Exception:
            return {queue_name: 0 for queue_name in self.QUEUE_KEYS.keys()}
        finally:
            await client.aclose()

    def check_queue_health(self, depths: dict[str, int]) -> dict[str, str]:
        statuses: dict[str, str] = {}
        for queue_name, depth in depths.items():
            if depth > self.ALERT_THRESHOLD * self.CRITICAL_THRESHOLD_MULTIPLIER:
                statuses[queue_name] = "critical"
                log.critical(
                    "celery_queue_depth_critical",
                    extra={"queue": queue_name, "depth": depth},
                )
            elif depth > self.ALERT_THRESHOLD:
                statuses[queue_name] = "warning"
                log.warning(
                    "celery_queue_depth_warning",
                    extra={"queue": queue_name, "depth": depth},
                )
            else:
                statuses[queue_name] = "ok"
        return statuses

    def on_task_failure(
        self,
        *,
        sender: Any = None,
        task_id: str | None = None,
        exception: Exception | None = None,
        args: tuple[Any, ...] | None = None,
        kwargs: dict[str, Any] | None = None,
        **_: Any,
    ) -> None:
        task_name = getattr(sender, "name", str(sender))
        tenant_id = None
        if kwargs:
            tenant_id = kwargs.get("tenant_id") or kwargs.get("tenant")

        log.error(
            "celery_task_failure",
            extra={
                "task_name": task_name,
                "task_id": task_id,
                "tenant_id": str(tenant_id) if tenant_id else None,
                "exception": str(exception) if exception else "unknown",
                "args_size": len(args or ()),
            },
        )
        if settings.SENTRY_DSN and exception is not None:
            sentry_sdk.capture_exception(exception)


@lru_cache
def get_celery_monitor() -> CeleryMonitor:
    return CeleryMonitor(redis_url=str(settings.REDIS_URL))


def connect_task_failure_signal() -> None:
    monitor = get_celery_monitor()

    @task_failure.connect(weak=False)
    def _task_failure_handler(
        sender: Any = None,
        task_id: str | None = None,
        exception: Exception | None = None,
        args: tuple[Any, ...] | None = None,
        kwargs: dict[str, Any] | None = None,
        **extra: Any,
    ) -> None:
        monitor.on_task_failure(
            sender=sender,
            task_id=task_id,
            exception=exception,
            args=args,
            kwargs=kwargs,
            **extra,
        )

