from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest


class _FakeRedisClient:
    def __init__(self) -> None:
        self.items: list[str] = []

    def lpush(self, key: str, payload: str) -> None:
        assert key == "finqor:dead_letter"
        self.items.insert(0, payload)

    def lrange(self, key: str, start: int, end: int) -> list[str]:
        assert key == "finqor:dead_letter"
        return list(self.items)

    def close(self) -> None:
        return None


@pytest.mark.unit
def test_on_task_failure_pushes_dead_letter_after_final_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    from financeops.observability.celery_monitor import CeleryMonitor

    fake_client = _FakeRedisClient()
    monkeypatch.setattr(
        "financeops.observability.celery_monitor.redis.Redis.from_url",
        lambda *args, **kwargs: fake_client,
    )

    monitor = CeleryMonitor("redis://localhost:6379/0")
    sender = SimpleNamespace(
        name="payment.retry_failed_payments",
        request=SimpleNamespace(retries=3),
        max_retries=3,
    )

    monitor.on_task_failure(
        sender=sender,
        task_id="task-123",
        exception=RuntimeError("boom"),
        args=(),
        kwargs={},
    )

    items = monitor.list_dead_letter_items()
    assert len(items) == 1
    assert items[0]["task_name"] == "payment.retry_failed_payments"
    assert items[0]["task_id"] == "task-123"
    assert items[0]["error"] == "boom"


@pytest.mark.unit
def test_check_dead_letter_queue_counts_stale_items(monkeypatch: pytest.MonkeyPatch) -> None:
    from financeops.tasks.celery_app import check_dead_letter_queue

    now = datetime.now(UTC)
    fake_monitor = SimpleNamespace(
        list_dead_letter_items=lambda: [
            {
                "task_name": "old.task",
                "task_id": "old-1",
                "error": "stale failure",
                "failed_at": (now - timedelta(hours=25)).isoformat(),
            },
            {
                "task_name": "fresh.task",
                "task_id": "fresh-1",
                "error": "fresh failure",
                "failed_at": (now - timedelta(hours=1)).isoformat(),
            },
        ]
    )
    monkeypatch.setattr(
        "financeops.tasks.celery_app.get_celery_monitor",
        lambda: fake_monitor,
    )

    result = check_dead_letter_queue.run()

    assert result == {"dead_letter_items": 2, "stale_items": 1}
