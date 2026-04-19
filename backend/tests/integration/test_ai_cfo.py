from __future__ import annotations

import asyncio
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import respx
from httpx import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from financeops.db.models.ai_cfo_layer import AiCfoLedger, AiCfoNarrativeBlock
from financeops.modules.ai_cfo_layer.application import narrative_service
from financeops.modules.ai_cfo_layer.domain.exceptions import AIResponseValidationError
from financeops.modules.ai_cfo_layer.infrastructure.ai_client import AIClient
from financeops.modules.ai_cfo_layer.tasks import generate_narrative_async_task


def _anthropic_payload(text: str) -> Response:
    return Response(
        200,
        json={
            "content": [{"type": "text", "text": text}],
            "usage": {"input_tokens": 100, "output_tokens": 50},
        },
    )


def _seeded_ai_client() -> AIClient:
    return AIClient(
        SimpleNamespace(
            anthropic_api_key="sk-ant-real",
            openai_api_key=None,
            deepseek_api_key=None,
        )
    )


def _patch_narrative_inputs(monkeypatch: pytest.MonkeyPatch) -> None:
    kpi_rows = [
        SimpleNamespace(metric_name="revenue", metric_value=Decimal("500.00")),
        SimpleNamespace(metric_name="net_profit", metric_value=Decimal("120.00")),
        SimpleNamespace(metric_name="net_margin", metric_value=Decimal("24.00")),
        SimpleNamespace(metric_name="operating_margin", metric_value=Decimal("28.00")),
    ]
    metric_variances = [
        SimpleNamespace(
            metric_name="revenue",
            current_value=Decimal("500.00"),
            previous_value=Decimal("450.00"),
            variance_value=Decimal("50.00"),
            variance_percent=Decimal("11.11"),
        )
    ]
    account_variances = [
        SimpleNamespace(
            account_code="4100",
            account_name="Revenue",
            current_value=Decimal("500.00"),
            previous_value=Decimal("450.00"),
            variance_value=Decimal("50.00"),
            variance_percent=Decimal("11.11"),
        )
    ]
    anomalies = SimpleNamespace(
        rows=[
            SimpleNamespace(
                severity="HIGH",
                anomaly_type="MARGIN_DEVIATION",
                explanation="Margin moved by 20.00",
            )
        ]
    )
    recommendations = SimpleNamespace(
        rows=[SimpleNamespace(message="Prioritize collections over the next cycle.")]
    )

    monkeypatch.setattr(
        narrative_service,
        "compute_kpis",
        AsyncMock(return_value=SimpleNamespace(rows=kpi_rows)),
    )
    monkeypatch.setattr(
        narrative_service,
        "compute_variance",
        AsyncMock(
            return_value=SimpleNamespace(
                metric_variances=metric_variances,
                account_variances=account_variances,
            )
        ),
    )
    monkeypatch.setattr(
        narrative_service,
        "detect_anomalies",
        AsyncMock(return_value=anomalies),
    )
    monkeypatch.setattr(
        narrative_service,
        "generate_recommendations",
        AsyncMock(return_value=recommendations),
    )


@pytest.mark.asyncio
@respx.mock
async def test_narrative_service_calls_claude_api_endpoint(
    async_session: AsyncSession,
    test_tenant,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_narrative_inputs(monkeypatch)
    route = respx.post("https://api.anthropic.com/v1/messages").mock(
        return_value=_anthropic_payload(
            '{"summary":"Revenue closed at 500.00 with net profit 120.00.",'
            '"highlights":["Revenue variance vs comparison period is 11.11% (50.00)."],'
            '"drivers":["4100 Revenue: variance 50.00 (11.11%)."],'
            '"risks":["MARGIN_DEVIATION: Margin moved by 20.00"],'
            '"actions":["Prioritize collections over the next cycle."]}'
        )
    )

    payload = await narrative_service.generate_narrative(
        async_session,
        tenant_id=test_tenant.id,
        actor_user_id=test_user.id,
        org_entity_id=None,
        org_group_id=None,
        from_date=date(2026, 3, 1),
        to_date=date(2026, 3, 31),
        ai_client=_seeded_ai_client(),
    )

    assert route.called is True
    assert payload.generation_method == "llm"
    assert payload.fact_basis["provider_used"] == "anthropic"


@pytest.mark.asyncio
@respx.mock
async def test_narrative_response_validated_against_source_data(
    async_session: AsyncSession,
    test_tenant,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_narrative_inputs(monkeypatch)
    respx.post("https://api.anthropic.com/v1/messages").mock(
        return_value=_anthropic_payload(
            '{"summary":"Revenue closed at 999.00 with net profit 120.00.",'
            '"highlights":["Revenue variance vs comparison period is 11.11% (50.00)."],'
            '"drivers":["4100 Revenue: variance 50.00 (11.11%)."],'
            '"risks":["MARGIN_DEVIATION: Margin moved by 20.00"],'
            '"actions":["Prioritize collections over the next cycle."]}'
        )
    )

    with pytest.raises(AIResponseValidationError):
        await narrative_service.generate_narrative(
            async_session,
            tenant_id=test_tenant.id,
            actor_user_id=test_user.id,
            org_entity_id=None,
            org_group_id=None,
            from_date=date(2026, 3, 1),
            to_date=date(2026, 3, 31),
            ai_client=_seeded_ai_client(),
        )


@pytest.mark.asyncio
@respx.mock
async def test_token_cost_inserted_in_ai_cfo_ledger(
    async_session: AsyncSession,
    test_tenant,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_narrative_inputs(monkeypatch)
    respx.post("https://api.anthropic.com/v1/messages").mock(
        return_value=_anthropic_payload(
            '{"summary":"Revenue closed at 500.00 with net profit 120.00.",'
            '"highlights":["Revenue variance vs comparison period is 11.11% (50.00)."],'
            '"drivers":["4100 Revenue: variance 50.00 (11.11%)."],'
            '"risks":["MARGIN_DEVIATION: Margin moved by 20.00"],'
            '"actions":["Prioritize collections over the next cycle."]}'
        )
    )

    await narrative_service.generate_narrative(
        async_session,
        tenant_id=test_tenant.id,
        actor_user_id=test_user.id,
        org_entity_id=None,
        org_group_id=None,
        from_date=date(2026, 3, 1),
        to_date=date(2026, 3, 31),
        ai_client=_seeded_ai_client(),
    )

    ledger_entry = (
        await async_session.execute(
            select(AiCfoLedger).where(AiCfoLedger.tenant_id == test_tenant.id)
        )
    ).scalar_one()
    narrative_block = (
        await async_session.execute(
            select(AiCfoNarrativeBlock).where(
                AiCfoNarrativeBlock.tenant_id == test_tenant.id
            )
        )
    ).scalar_one()

    assert ledger_entry.provider == "anthropic"
    assert ledger_entry.model == "claude-3-5-haiku-20241022"
    assert ledger_entry.prompt_tokens == 100
    assert ledger_entry.completion_tokens == 50
    assert narrative_block.provider == "anthropic"
    assert narrative_block.llm_model == "claude-3-5-haiku-20241022"


@pytest.mark.asyncio
@respx.mock
async def test_generate_narrative_async_task_uses_ai_client(
    api_test_tenant,
    api_test_user,
    api_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from financeops.modules.ai_cfo_layer import tasks as ai_tasks

    _patch_narrative_inputs(monkeypatch)
    monkeypatch.setattr(ai_tasks.settings, "AI_CFO_ENABLED", True)
    monkeypatch.setattr(ai_tasks.settings, "ANTHROPIC_API_KEY", "sk-ant-real")
    monkeypatch.setattr(ai_tasks.settings, "OPENAI_API_KEY", None)
    monkeypatch.setattr(ai_tasks.settings, "DEEPSEEK_API_KEY", None)
    respx.post("https://api.anthropic.com/v1/messages").mock(
        return_value=_anthropic_payload(
            '{"summary":"Revenue closed at 500.00 with net profit 120.00.",'
            '"highlights":["Revenue variance vs comparison period is 11.11% (50.00)."],'
            '"drivers":["4100 Revenue: variance 50.00 (11.11%)."],'
            '"risks":["MARGIN_DEVIATION: Margin moved by 20.00"],'
            '"actions":["Prioritize collections over the next cycle."]}'
        )
    )

    result = await asyncio.to_thread(
        generate_narrative_async_task,
        tenant_id=str(api_test_tenant.id),
        actor_user_id=str(api_test_user.id),
        org_entity_id=None,
        org_group_id=None,
        from_date="2026-03-01",
        to_date="2026-03-31",
        comparison="prev_month",
    )

    assert result["generation_method"] == "llm"
    assert result["fact_basis"]["provider_used"] == "anthropic"

    async with api_session_factory() as session:
        ledger_entry = (
            await session.execute(
                select(AiCfoLedger).where(AiCfoLedger.tenant_id == api_test_tenant.id)
            )
        ).scalar_one()
        assert ledger_entry.provider == "anthropic"
