from __future__ import annotations

import pytest

from financeops.llm.cache import CACHE_TTL_SECONDS, compute_cache_key
from financeops.llm.gateway import execute_with_cache


class _FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.ttl: dict[str, int] = {}

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self.store[key] = value
        self.ttl[key] = ttl


def test_cache_key_is_deterministic() -> None:
    """Same inputs always produce the same cache key."""
    key1 = compute_cache_key("classification", "test prompt", "system", "gpt-4o-mini")
    key2 = compute_cache_key("classification", "test prompt", "system", "gpt-4o-mini")
    assert key1 == key2


def test_cache_key_differs_on_prompt_change() -> None:
    """Prompt changes produce different cache keys."""
    assert compute_cache_key("classification", "A", "sys", "model") != compute_cache_key(
        "classification", "B", "sys", "model"
    )


def test_cache_key_differs_on_model_change() -> None:
    """Model changes produce different cache keys."""
    assert compute_cache_key("classification", "A", "sys", "model-a") != compute_cache_key(
        "classification", "A", "sys", "model-b"
    )


def test_cache_key_differs_on_task_type_change() -> None:
    """Task type changes produce different cache keys."""
    assert compute_cache_key("classification", "A", "sys", "model") != compute_cache_key(
        "commentary", "A", "sys", "model"
    )


@pytest.mark.asyncio
async def test_cache_hit_skips_llm_call() -> None:
    """Cache hit returns cached response and does not invoke fallback."""
    redis = _FakeRedis()
    key = compute_cache_key("classification", "prompt", "sys", "gpt")
    redis.store[key] = "cached value"
    called = {"n": 0}

    async def _fallback() -> str:
        called["n"] += 1
        return "live value"

    response, was_cached = await execute_with_cache(
        task_type="classification",
        prompt="prompt",
        system_prompt="sys",
        model="gpt",
        redis_client=redis,
        fallback_fn=_fallback,
    )
    assert was_cached is True
    assert response == "cached value"
    assert called["n"] == 0


@pytest.mark.asyncio
async def test_cache_miss_calls_llm_and_stores() -> None:
    """Cache miss invokes fallback and stores output."""
    redis = _FakeRedis()
    called = {"n": 0}

    async def _fallback() -> str:
        called["n"] += 1
        return "test response"

    response, was_cached = await execute_with_cache(
        task_type="classification",
        prompt="novel",
        system_prompt="sys",
        model="gpt",
        redis_client=redis,
        fallback_fn=_fallback,
    )
    key = compute_cache_key("classification", "novel", "sys", "gpt")
    assert response == "test response"
    assert was_cached is False
    assert called["n"] == 1
    assert redis.store[key] == "test response"


@pytest.mark.asyncio
async def test_cache_without_redis_executes_fallback() -> None:
    """No redis client still returns fallback output."""
    called = {"n": 0}

    async def _fallback() -> str:
        called["n"] += 1
        return "x"

    response, was_cached = await execute_with_cache(
        task_type="classification",
        prompt="a",
        system_prompt="b",
        model="c",
        redis_client=None,
        fallback_fn=_fallback,
    )
    assert response == "x"
    assert was_cached is False
    assert called["n"] == 1


def test_standards_lookup_cached_24_hours() -> None:
    """Standards lookup cache TTL is 24h."""
    key = compute_cache_key("standards_lookup", "IFRS 16", "sys", "model")
    assert key.startswith("ai_cache:")
    assert CACHE_TTL_SECONDS["standards_lookup"] == 86400


def test_commentary_ttl_is_30_minutes() -> None:
    """Commentary cache TTL is 30 minutes."""
    assert CACHE_TTL_SECONDS["commentary"] == 1800


def test_classification_ttl_is_1_hour() -> None:
    """Classification cache TTL is 1 hour."""
    assert CACHE_TTL_SECONDS["classification"] == 3600


def test_cache_key_has_ai_cache_prefix() -> None:
    """Cache key format uses ai_cache prefix."""
    assert compute_cache_key("classification", "p", "s", "m").startswith("ai_cache:")


@pytest.mark.asyncio
async def test_default_ttl_used_for_unknown_task() -> None:
    """Unknown task type uses default TTL."""
    redis = _FakeRedis()

    async def _fallback() -> str:
        return "ok"

    await execute_with_cache(
        task_type="unknown_task",
        prompt="p",
        system_prompt="s",
        model="m",
        redis_client=redis,
        fallback_fn=_fallback,
    )
    key = compute_cache_key("unknown_task", "p", "s", "m")
    assert redis.ttl[key] == CACHE_TTL_SECONDS["default"]


@pytest.mark.asyncio
async def test_cache_hit_counter_path_safe_without_metrics_module(monkeypatch) -> None:
    """Cache hit path still works if metrics import fails."""
    redis = _FakeRedis()
    key = compute_cache_key("classification", "p", "s", "m")
    redis.store[key] = "cached"

    real_import = __import__

    def _fake_import(name, *args, **kwargs):  # type: ignore[no-untyped-def]
        if name == "financeops.observability.business_metrics":
            raise ImportError("forced")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", _fake_import)

    async def _fallback() -> str:
        return "live"

    response, was_cached = await execute_with_cache(
        task_type="classification",
        prompt="p",
        system_prompt="s",
        model="m",
        redis_client=redis,
        fallback_fn=_fallback,
    )
    assert response == "cached"
    assert was_cached is True
