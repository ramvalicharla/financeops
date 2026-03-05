from __future__ import annotations

import logging

from financeops.llm.circuit_breaker import CircuitBreakerRegistry
from financeops.llm.fallback import execute_with_fallback, AIResult
from financeops.llm.pipeline import PipelineContext, PipelineResult, run_pipeline

log = logging.getLogger(__name__)

# Module-level registry — uses Redis when available, falls back to in-process dict
_registry: CircuitBreakerRegistry | None = None


def get_circuit_registry(redis_client=None) -> CircuitBreakerRegistry:
    global _registry
    if _registry is None:
        _registry = CircuitBreakerRegistry(redis_client=redis_client)
    return _registry


async def gateway_generate(
    *,
    task_type: str,
    prompt: str,
    system_prompt: str,
    tenant_id: str,
    redis_client=None,
) -> AIResult:
    """
    Top-level gateway entry point for single-shot LLM requests (no pipeline).
    Uses circuit breaker + fallback chain.
    """
    registry = get_circuit_registry(redis_client)
    return await execute_with_fallback(
        task_type=task_type,
        prompt=prompt,
        system_prompt=system_prompt,
        tenant_id=tenant_id,
        circuit_registry=registry,
    )


async def gateway_pipeline(
    ctx: PipelineContext,
    redis_client=None,
) -> PipelineResult:
    """
    Top-level gateway entry point for the full 5-stage pipeline.
    """
    registry = get_circuit_registry(redis_client)
    return await run_pipeline(ctx, registry)
