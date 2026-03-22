from __future__ import annotations

import uuid

import pytest

from financeops.llm.circuit_breaker import CircuitBreakerRegistry


@pytest.mark.asyncio
async def test_circuit_breaker_state_stored_in_redis(redis_client) -> None:
    """Circuit breaker state persists in Redis, not module memory."""
    provider = "anthropic"
    model = f"claude-sonnet-{uuid.uuid4()}"
    registry = CircuitBreakerRegistry(redis_client=redis_client)
    await registry.record_failure(provider, model)

    registry2 = CircuitBreakerRegistry(redis_client=redis_client)
    state = await registry2.get_state(provider, model)
    assert state.failure_count == 1


def test_no_module_level_registry_global() -> None:
    """gateway.py has no module-level _registry variable."""
    import financeops.llm.gateway as gw

    assert not hasattr(gw, "_registry")


@pytest.mark.asyncio
async def test_two_workers_share_circuit_state(redis_client) -> None:
    """Circuit opened by one registry instance is seen by another."""
    provider = "openai"
    model = f"gpt-4o-{uuid.uuid4()}"
    registry1 = CircuitBreakerRegistry(redis_client=redis_client)
    registry2 = CircuitBreakerRegistry(redis_client=redis_client)

    for _ in range(5):
        await registry1.record_failure(provider, model)

    assert await registry2.is_open(provider, model) is True

