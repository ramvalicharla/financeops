from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.ai_cost import AICostEvent, TenantTokenBudget

# Cost per 1M tokens (USD)
MODEL_COSTS_PER_1M_TOKENS: dict[str, dict[str, Decimal]] = {
    # Anthropic — claude-haiku-4-5-20251001: $0.80/$4.00 per 1M (source: Anthropic pricing, 2025-10)
    "claude-haiku-4-5-20251001": {
        "prompt": Decimal("0.800"),
        "completion": Decimal("4.000"),
    },
    # Anthropic — claude-sonnet-4-5-20251001: $3.00/$15.00 per 1M (source: Anthropic pricing, 2025-10)
    "claude-sonnet-4-5-20251001": {
        "prompt": Decimal("3.000"),
        "completion": Decimal("15.000"),
    },
    # Anthropic — claude-opus-4-5-20251001: $15.00/$75.00 per 1M (source: Anthropic pricing, 2025-10)
    "claude-opus-4-5-20251001": {
        "prompt": Decimal("15.000"),
        "completion": Decimal("75.000"),
    },
    # OpenAI — source: OpenAI pricing page, 2025-10
    "gpt-4o": {
        "prompt": Decimal("5.000"),
        "completion": Decimal("15.000"),
    },
    "gpt-4o-mini": {
        "prompt": Decimal("0.150"),
        "completion": Decimal("0.600"),
    },
    # Google Gemini — source: Google AI pricing page, 2025-10 (prompts ≤128K tokens)
    "gemini-1.5-pro": {
        "prompt": Decimal("3.500"),
        "completion": Decimal("10.500"),
    },
    "gemini-1.5-flash": {
        "prompt": Decimal("0.350"),
        "completion": Decimal("1.050"),
    },
    # Ollama — local inference, no token cost
    "ollama": {
        "prompt": Decimal("0"),
        "completion": Decimal("0"),
    },
}


def compute_cost(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    provider: str = "",
) -> Decimal:
    # Local Ollama models have no cost regardless of model name
    if provider == "ollama" or model in MODEL_COSTS_PER_1M_TOKENS.get("ollama", {}):
        costs = MODEL_COSTS_PER_1M_TOKENS["ollama"]
    else:
        costs = MODEL_COSTS_PER_1M_TOKENS.get(
            model,
            {
                "prompt": Decimal("1.000"),
                "completion": Decimal("3.000"),
            },
        )
    prompt_cost = Decimal(str(prompt_tokens)) / Decimal("1000000") * costs["prompt"]
    completion_cost = (
        Decimal(str(completion_tokens)) / Decimal("1000000") * costs["completion"]
    )
    return (prompt_cost + completion_cost).quantize(Decimal("0.000001"))


async def _ensure_budget_row(session: AsyncSession, tenant_id: UUID) -> TenantTokenBudget:
    budget = await session.get(TenantTokenBudget, tenant_id)
    if budget is not None:
        return budget
    budget = TenantTokenBudget(
        tenant_id=tenant_id,
        budget_period_start=date.today().replace(day=1),
    )
    session.add(budget)
    await session.flush()
    return budget


async def record_ai_call(
    session: AsyncSession,
    tenant_id: UUID,
    task_type: str,
    provider: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    *,
    was_cached: bool = False,
    was_fallback: bool = False,
    pii_was_masked: bool = False,
    pipeline_run_id: UUID | None = None,
) -> AICostEvent:
    cost = compute_cost(model, prompt_tokens, completion_tokens, provider=provider)
    event = AICostEvent(
        tenant_id=tenant_id,
        task_type=task_type,
        provider=provider,
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
        cost_usd=cost,
        was_cached=was_cached,
        was_fallback=was_fallback,
        pii_was_masked=pii_was_masked,
        pipeline_run_id=pipeline_run_id,
    )
    session.add(event)

    await _ensure_budget_row(session, tenant_id)
    await session.execute(
        update(TenantTokenBudget)
        .where(TenantTokenBudget.tenant_id == tenant_id)
        .values(
            current_month_tokens=TenantTokenBudget.current_month_tokens
            + (prompt_tokens + completion_tokens),
            current_month_cost_usd=TenantTokenBudget.current_month_cost_usd + cost,
            updated_at=datetime.now(UTC),
        )
    )
    await session.flush()
    return event


async def check_budget(
    session: AsyncSession,
    tenant_id: UUID,
) -> dict[str, Decimal | str | bool]:
    budget = await session.get(TenantTokenBudget, tenant_id)
    if budget is None:
        return {
            "allowed": True,
            "reason": "no_budget_configured",
            "usage_pct": Decimal("0"),
        }

    if budget.monthly_cost_limit_usd == Decimal("0"):
        usage_pct = Decimal("100.00")
    else:
        usage_pct = (
            budget.current_month_cost_usd
            / budget.monthly_cost_limit_usd
            * Decimal("100")
        ).quantize(Decimal("0.01"))

    if budget.hard_stop_on_budget and usage_pct >= Decimal("100"):
        return {
            "allowed": False,
            "reason": "monthly_budget_exhausted",
            "usage_pct": usage_pct,
        }
    return {"allowed": True, "reason": "within_budget", "usage_pct": usage_pct}


async def reset_monthly_budgets(session: AsyncSession, today: date | None = None) -> int:
    check_date = today or date.today()
    current_period_start = check_date.replace(day=1)
    stale_ids = (
        await session.execute(
            select(TenantTokenBudget.tenant_id).where(
                TenantTokenBudget.budget_period_start < current_period_start
            )
        )
    ).scalars().all()
    if not stale_ids:
        return 0
    await session.execute(
        update(TenantTokenBudget)
        .where(TenantTokenBudget.tenant_id.in_(stale_ids))
        .values(
            current_month_tokens=0,
            current_month_cost_usd=Decimal("0"),
            budget_period_start=current_period_start,
            updated_at=datetime.now(UTC),
        )
    )
    await session.flush()
    return len(stale_ids)

