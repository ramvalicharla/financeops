from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
import uuid

import pytest
from sqlalchemy import text, update
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.append_only import append_only_function_sql, create_trigger_sql, drop_trigger_sql
from financeops.db.models.ai_cost import AICostEvent, TenantTokenBudget
from financeops.llm.cost_ledger import (
    check_budget,
    compute_cost,
    record_ai_call,
    reset_monthly_budgets,
)


def test_cost_computed_in_decimal() -> None:
    """AI cost computation uses Decimal."""
    cost = compute_cost("gpt-4o-mini", 1000, 500)
    assert isinstance(cost, Decimal)
    assert cost == Decimal("0.000450")


def test_ollama_costs_zero() -> None:
    """Local Ollama calls are zero-cost."""
    assert compute_cost("ollama", 10000, 5000) == Decimal("0")


def test_unknown_model_uses_default_rates() -> None:
    """Unknown model falls back to default per-1M rates."""
    cost = compute_cost("unknown", 1000000, 1000000)
    assert cost == Decimal("4.000000")


@pytest.mark.asyncio
async def test_ai_call_recorded_in_ledger(
    async_session: AsyncSession,
    test_tenant,
) -> None:
    """record_ai_call creates immutable cost event row."""
    event = await record_ai_call(
        session=async_session,
        tenant_id=test_tenant.id,
        task_type="classification",
        provider="openai",
        model="gpt-4o-mini",
        prompt_tokens=1000,
        completion_tokens=500,
    )
    assert isinstance(event.cost_usd, Decimal)
    fetched = await async_session.get(AICostEvent, event.id)
    assert fetched is not None
    assert fetched.cost_usd == Decimal("0.000450")


@pytest.mark.asyncio
async def test_record_ai_call_updates_budget_totals(async_session: AsyncSession, test_tenant) -> None:
    """record_ai_call updates running monthly totals."""
    await record_ai_call(
        session=async_session,
        tenant_id=test_tenant.id,
        task_type="classification",
        provider="openai",
        model="gpt-4o-mini",
        prompt_tokens=1000,
        completion_tokens=500,
    )
    budget = await async_session.get(TenantTokenBudget, test_tenant.id)
    assert budget is not None
    assert budget.current_month_tokens == 1500
    assert budget.current_month_cost_usd == Decimal("0.000450")


@pytest.mark.asyncio
async def test_budget_check_blocks_at_100_pct(async_session: AsyncSession, test_tenant) -> None:
    """hard_stop_on_budget blocks calls at 100% usage."""
    budget = TenantTokenBudget(
        tenant_id=test_tenant.id,
        monthly_cost_limit_usd=Decimal("10.00"),
        current_month_cost_usd=Decimal("10.00"),
        budget_period_start=date.today().replace(day=1),
        hard_stop_on_budget=True,
    )
    async_session.add(budget)
    await async_session.flush()
    status = await check_budget(async_session, test_tenant.id)
    assert status["allowed"] is False
    assert status["reason"] == "monthly_budget_exhausted"


@pytest.mark.asyncio
async def test_budget_check_allows_without_hard_stop(async_session: AsyncSession, test_tenant) -> None:
    """Without hard stop, budget can exceed limit."""
    budget = TenantTokenBudget(
        tenant_id=test_tenant.id,
        monthly_cost_limit_usd=Decimal("10.00"),
        current_month_cost_usd=Decimal("10.00"),
        budget_period_start=date.today().replace(day=1),
        hard_stop_on_budget=False,
    )
    async_session.add(budget)
    await async_session.flush()
    status = await check_budget(async_session, test_tenant.id)
    assert status["allowed"] is True
    assert status["reason"] == "within_budget"


@pytest.mark.asyncio
async def test_budget_check_allows_when_missing(async_session: AsyncSession, test_tenant) -> None:
    """Missing budget row allows invocation."""
    status = await check_budget(async_session, test_tenant.id)
    assert status["allowed"] is True
    assert status["reason"] == "no_budget_configured"


@pytest.mark.asyncio
async def test_ai_cost_event_is_append_only(async_session: AsyncSession, test_tenant) -> None:
    """ai_cost_events blocks UPDATE once append-only trigger is attached."""
    await async_session.execute(text(append_only_function_sql()))
    await async_session.execute(text(drop_trigger_sql("ai_cost_events")))
    await async_session.execute(text(create_trigger_sql("ai_cost_events")))
    event = await record_ai_call(
        session=async_session,
        tenant_id=test_tenant.id,
        task_type="classification",
        provider="openai",
        model="gpt-4o-mini",
        prompt_tokens=1000,
        completion_tokens=500,
    )
    await async_session.flush()
    with pytest.raises(Exception):
        await async_session.execute(
            update(AICostEvent).where(AICostEvent.id == event.id).values(task_type="changed")
        )


@pytest.mark.asyncio
async def test_budget_monthly_reset(async_session: AsyncSession, test_tenant) -> None:
    """Monthly reset zeroes counters when period rolls over."""
    budget = TenantTokenBudget(
        tenant_id=test_tenant.id,
        monthly_token_limit=1000,
        monthly_cost_limit_usd=Decimal("5.00"),
        current_month_tokens=321,
        current_month_cost_usd=Decimal("1.234000"),
        budget_period_start=(date.today().replace(day=1) - timedelta(days=32)).replace(day=1),
    )
    async_session.add(budget)
    await async_session.flush()
    changed = await reset_monthly_budgets(async_session)
    assert changed == 1
    refreshed = await async_session.get(TenantTokenBudget, test_tenant.id)
    assert refreshed is not None
    assert refreshed.current_month_tokens == 0
    assert refreshed.current_month_cost_usd == Decimal("0")


@pytest.mark.asyncio
async def test_budget_monthly_reset_noop_for_current_period(async_session: AsyncSession, test_tenant) -> None:
    """Reset is no-op when already in current period."""
    budget = TenantTokenBudget(
        tenant_id=test_tenant.id,
        current_month_tokens=10,
        current_month_cost_usd=Decimal("0.100000"),
        budget_period_start=date.today().replace(day=1),
    )
    async_session.add(budget)
    await async_session.flush()
    changed = await reset_monthly_budgets(async_session)
    assert changed == 0


@pytest.mark.asyncio
async def test_record_flags_persist(async_session: AsyncSession, test_tenant) -> None:
    """Fallback/cache/masking flags are persisted on cost events."""
    event = await record_ai_call(
        session=async_session,
        tenant_id=test_tenant.id,
        task_type="classification",
        provider="openai",
        model="gpt-4o-mini",
        prompt_tokens=10,
        completion_tokens=5,
        was_cached=True,
        was_fallback=True,
        pii_was_masked=True,
        pipeline_run_id=uuid.uuid4(),
    )
    assert event.was_cached is True
    assert event.was_fallback is True
    assert event.pii_was_masked is True

