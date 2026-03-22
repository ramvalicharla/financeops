from __future__ import annotations

from decimal import Decimal

from financeops.observability.business_metrics import (
    ai_cost_counter,
    ai_tokens_counter,
)


def observe_ai_cost(
    *,
    provider: str,
    model: str,
    task_type: str,
    cost_usd: Decimal,
) -> None:
    ai_cost_counter.labels(
        provider=provider,
        model=model,
        task_type=task_type,
    ).inc(float(cost_usd))


def observe_ai_tokens(
    *,
    provider: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> None:
    ai_tokens_counter.labels(
        provider=provider,
        model=model,
        token_type="prompt",
    ).inc(prompt_tokens)
    ai_tokens_counter.labels(
        provider=provider,
        model=model,
        token_type="completion",
    ).inc(completion_tokens)

