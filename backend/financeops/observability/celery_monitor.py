from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any

import redis
import redis.asyncio as aioredis
import sentry_sdk
from celery.signals import task_failure

from financeops.config import settings

log = logging.getLogger(__name__)


class CeleryMonitor:
    ALERT_THRESHOLD = 100
    CRITICAL_THRESHOLD_MULTIPLIER = 5
    DEAD_LETTER_KEY = "finqor:dead_letter"
    QUEUE_KEYS: dict[str, str] = {
        "default": "celery",
        "financial": "financial",
        "sync": "sync",
        "notifications": "notifications",
        "dead_letter": "dead_letter",
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
        except Exception as exc:
            log.error("celery_queue_depth_probe_failed", extra={"error": str(exc)})
            raise RuntimeError(f"Redis queue depth probe failed: {exc}") from exc
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

    @staticmethod
    def classify_workload(task_name: str | None) -> str:
        name = (task_name or "").strip().lower()
        if name.startswith("payment."):
            return "payment"
        if "webhook" in name:
            return "webhook"
        return "other"

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
        self._push_dead_letter_item(
            sender=sender,
            task_id=task_id,
            exception=exception,
        )

    def list_dead_letter_items(self) -> list[dict[str, Any]]:
        client = redis.Redis.from_url(
            self._redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
        try:
            rows = client.lrange(self.DEAD_LETTER_KEY, 0, -1)
            items: list[dict[str, Any]] = []
            for row in rows:
                if not row:
                    continue
                try:
                    payload = json.loads(row)
                except json.JSONDecodeError:
                    items.append({"raw": row, "decode_error": True})
                    continue
                if isinstance(payload, dict):
                    items.append(payload)
            return items
        finally:
            client.close()

    def list_dead_letter_items_for_workloads(
        self,
        *,
        workloads: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        items = self.list_dead_letter_items()
        if not workloads:
            return items
        normalized = {value.strip().lower() for value in workloads if value and value.strip()}
        return [
            item
            for item in items
            if self.classify_workload(str(item.get("task_name") or "")) in normalized
        ]

    def _push_dead_letter_item(
        self,
        *,
        sender: Any,
        task_id: str | None,
        exception: Exception | None,
    ) -> None:
        request = getattr(sender, "request", None)
        retries = int(getattr(request, "retries", 0) or 0)
        max_retries = getattr(sender, "max_retries", None)
        if max_retries is None or retries < int(max_retries):
            return

        client = redis.Redis.from_url(
            self._redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
        try:
            client.lpush(
                self.DEAD_LETTER_KEY,
                json.dumps(
                    {
                        "task_name": getattr(sender, "name", str(sender)),
                        "task_id": str(task_id) if task_id is not None else "",
                        "error": str(exception) if exception else "unknown",
                        "failed_at": datetime.now(UTC).isoformat(),
                        "tenant_id": str(getattr(request, "kwargs", {}).get("tenant_id") or ""),
                        "correlation_id": str(getattr(request, "kwargs", {}).get("correlation_id") or ""),
                        "retries": retries,
                        "max_retries": int(max_retries),
                        "workload": self.classify_workload(getattr(sender, "name", str(sender))),
                    }
                ),
            )
        except Exception as exc:  # pragma: no cover - defensive logging path
            log.error("celery_dead_letter_push_failed", extra={"error": str(exc)})
        finally:
            client.close()


@lru_cache
def get_celery_monitor() -> CeleryMonitor:
    return CeleryMonitor(redis_url=settings.redis_cache_url)


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
