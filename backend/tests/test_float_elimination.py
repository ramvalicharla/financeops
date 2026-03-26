from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.prompts import AiPromptVersion
from financeops.llm.circuit_breaker import CircuitBreakerRegistry
from financeops.llm.fallback import AIResult
from financeops.llm.pipeline import (
    AGREEMENT_THRESHOLD,
    PipelineContext,
    PipelineResult,
    run_pipeline,
)
from financeops.services.fixed_assets.depreciation_methods.reducing_balance import (
    compute_monthly_rate,
)


@pytest.mark.asyncio
async def test_reducing_balance_monthly_rate_is_decimal() -> None:
    """Monthly rate computation returns Decimal, never float."""
    result = compute_monthly_rate(Decimal("0.25"))
    assert isinstance(result, Decimal)
    assert result == result.quantize(Decimal("0.000001"))


@pytest.mark.asyncio
async def test_reducing_balance_known_value() -> None:
    """25% annual WDV rate produces expected monthly Decimal rate."""
    result = compute_monthly_rate(Decimal("0.25"))
    assert abs(result - Decimal("0.023688")) < Decimal("0.000001")


@pytest.mark.asyncio
async def test_acceptance_rate_stored_as_numeric(async_session: AsyncSession) -> None:
    """AiPromptVersion.acceptance_rate stores and retrieves as Decimal."""
    row = AiPromptVersion(
        prompt_key="float-elimination-test",
        version=1,
        prompt_text="test",
        model_target="gpt",
        is_active=True,
        acceptance_rate=Decimal("0.9123"),
    )
    async_session.add(row)
    await async_session.flush()
    await async_session.refresh(row)

    assert isinstance(row.acceptance_rate, Decimal)
    assert row.acceptance_rate == Decimal("0.9123")


@pytest.mark.asyncio
async def test_pipeline_agreement_score_is_decimal() -> None:
    """PipelineResult.agreement_score uses Decimal comparison."""
    assert isinstance(AGREEMENT_THRESHOLD, Decimal)
    result = PipelineResult(
        status="COMPLETED",
        output_data={},
        stage2_model="model-a",
        stage3_model="model-b",
        agreement_score=Decimal("0.9000"),
        total_duration_ms=1.0,
        credits_used=Decimal("0.100000"),
    )
    assert result.agreement_score > AGREEMENT_THRESHOLD


@pytest.mark.asyncio
async def test_agreement_score_boundary_exact(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_gateway_generate(**kwargs):  # type: ignore[no-untyped-def]
        task_type = kwargs.get("task_type")
        content = "same output"
        if task_type == "validation":
            content = "same output"
        return AIResult(
            content=content,
            model_used="model-x",
            provider="test",
            was_fallback=False,
            attempt_number=1,
            duration_ms=1.0,
            tokens_used=100,
        )

    monkeypatch.setattr("financeops.llm.gateway.gateway_generate", _fake_gateway_generate)
    monkeypatch.setattr("financeops.llm.pipeline._compute_agreement", lambda *_: Decimal("0.8500"))
    result = await run_pipeline(
        PipelineContext(task_type="classification", tenant_id="tenant-1", user_id="user-1", input_data={"a": 1}),
        CircuitBreakerRegistry(redis_client=None),
    )
    assert result.status == "COMPLETED"
    assert result.agreement_score == Decimal("0.8500")


@pytest.mark.asyncio
async def test_agreement_score_below_boundary(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_gateway_generate(**kwargs):  # type: ignore[no-untyped-def]
        return AIResult(
            content="output",
            model_used="model-x",
            provider="test",
            was_fallback=False,
            attempt_number=1,
            duration_ms=1.0,
            tokens_used=100,
        )

    monkeypatch.setattr("financeops.llm.gateway.gateway_generate", _fake_gateway_generate)
    monkeypatch.setattr("financeops.llm.pipeline._compute_agreement", lambda *_: Decimal("0.8499"))
    result = await run_pipeline(
        PipelineContext(task_type="classification", tenant_id="tenant-1", user_id="user-1", input_data={"a": 1}),
        CircuitBreakerRegistry(redis_client=None),
    )
    assert result.status == "PENDING_REVIEW"
    assert result.agreement_score == Decimal("0.8499")


@pytest.mark.asyncio
async def test_agreement_score_is_decimal_not_float() -> None:
    result = PipelineResult(
        status="COMPLETED",
        output_data={},
        stage2_model="model-a",
        stage3_model="model-b",
        agreement_score=Decimal("0.8500"),
        total_duration_ms=1.0,
        credits_used=Decimal("0.100000"),
    )
    assert isinstance(result.agreement_score, Decimal)


def test_no_float_in_financial_service_imports() -> None:
    """No math.pow or float() calls in financial service modules."""
    pattern = re.compile(r"math\.pow|float\(")
    root = Path("financeops/services")
    hits: list[str] = []
    for file_path in root.rglob("*.py"):
        content = file_path.read_text(encoding="utf-8")
        if pattern.search(content):
            hits.append(str(file_path))

    assert not hits, f"Float contamination found in services: {hits}"
