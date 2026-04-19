from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
import respx
from httpx import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.ai_cfo_layer import AiCfoLedger
from financeops.modules.ai_cfo_layer.domain.exceptions import AIProviderUnavailableError
from financeops.modules.ai_cfo_layer.infrastructure.ai_client import (
    AIClient,
    AIResponse,
    record_ai_cfo_ledger_entry,
)


def _settings(
    *,
    enabled: bool = True,
    anthropic: str | None = None,
    openai: str | None = None,
    deepseek: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        ai_cfo_enabled=enabled,
        anthropic_api_key=anthropic,
        openai_api_key=openai,
        deepseek_api_key=deepseek,
    )


def _anthropic_ok(text: str = "Mock narrative text.") -> Response:
    return Response(
        200,
        json={
            "content": [{"type": "text", "text": text}],
            "usage": {"input_tokens": 100, "output_tokens": 50},
        },
    )


def _openai_ok(text: str = "Mock narrative text.") -> Response:
    return Response(
        200,
        json={
            "choices": [{"message": {"content": text}}],
            "usage": {"prompt_tokens": 110, "completion_tokens": 55},
        },
    )


def _deepseek_ok(text: str = "Mock narrative text.") -> Response:
    return Response(
        200,
        json={
            "choices": [{"message": {"content": text}}],
            "usage": {"prompt_tokens": 120, "completion_tokens": 60},
        },
    )


@pytest.mark.asyncio
@respx.mock
async def test_anthropic_used_when_key_configured() -> None:
    respx.post("https://api.anthropic.com/v1/messages").mock(return_value=_anthropic_ok())
    client = AIClient(
        _settings(
            anthropic="sk-ant-real",
            openai="sk-openai-real",
            deepseek="sk-deepseek-real",
        )
    )

    response = await client.complete("system", "user")

    assert response.provider_used == "anthropic"
    assert response.model_used == "claude-3-5-haiku-20241022"


@pytest.mark.asyncio
@respx.mock
async def test_falls_back_to_openai_when_anthropic_fails() -> None:
    respx.post("https://api.anthropic.com/v1/messages").mock(return_value=Response(500))
    respx.post("https://api.openai.com/v1/chat/completions").mock(return_value=_openai_ok())
    client = AIClient(
        _settings(
            anthropic="sk-ant-real",
            openai="sk-openai-real",
            deepseek="sk-deepseek-real",
        )
    )

    response = await client.complete("system", "user")

    assert response.provider_used == "openai"
    assert response.model_used == "gpt-4o-mini"


@pytest.mark.asyncio
@respx.mock
async def test_falls_back_to_deepseek_when_anthropic_and_openai_fail() -> None:
    respx.post("https://api.anthropic.com/v1/messages").mock(return_value=Response(500))
    respx.post("https://api.openai.com/v1/chat/completions").mock(return_value=Response(500))
    respx.post("https://api.deepseek.com/v1/chat/completions").mock(return_value=_deepseek_ok())
    client = AIClient(
        _settings(
            anthropic="sk-ant-real",
            openai="sk-openai-real",
            deepseek="sk-deepseek-real",
        )
    )

    response = await client.complete("system", "user")

    assert response.provider_used == "deepseek"
    assert response.model_used == "deepseek-chat"


@pytest.mark.asyncio
@respx.mock
async def test_raises_when_all_providers_fail() -> None:
    respx.post("https://api.anthropic.com/v1/messages").mock(return_value=Response(500))
    respx.post("https://api.openai.com/v1/chat/completions").mock(return_value=Response(500))
    respx.post("https://api.deepseek.com/v1/chat/completions").mock(return_value=Response(500))
    client = AIClient(
        _settings(
            anthropic="sk-ant-real",
            openai="sk-openai-real",
            deepseek="sk-deepseek-real",
        )
    )

    with pytest.raises(AIProviderUnavailableError):
        await client.complete("system", "user")


@pytest.mark.asyncio
@respx.mock
async def test_skips_placeholder_key_provider() -> None:
    anthropic_route = respx.post("https://api.anthropic.com/v1/messages").mock(
        return_value=_anthropic_ok()
    )
    openai_route = respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=_openai_ok()
    )
    client = AIClient(
        _settings(
            anthropic="sk-ant-PLACEHOLDER-update-before-launch",
            openai="sk-openai-real",
            deepseek=None,
        )
    )

    response = await client.complete("system", "user")

    assert [provider.name for provider in client.providers] == ["openai"]
    assert response.provider_used == "openai"
    assert anthropic_route.called is False
    assert openai_route.called is True


@pytest.mark.asyncio
async def test_provider_used_logged_in_ai_cfo_ledger(
    async_session: AsyncSession,
    test_tenant,
) -> None:
    response = AIResponse(
        text="Mock narrative text.",
        provider_used="openai",
        model_used="gpt-4o-mini",
        prompt_tokens=111,
        completion_tokens=56,
    )

    await record_ai_cfo_ledger_entry(
        async_session,
        tenant_id=test_tenant.id,
        feature="narrative",
        response=response,
    )

    entry = (
        await async_session.execute(
            select(AiCfoLedger).where(
                AiCfoLedger.tenant_id == test_tenant.id,
                AiCfoLedger.provider == "openai",
            )
        )
    ).scalar_one()

    assert entry.feature == "narrative"
    assert entry.model == "gpt-4o-mini"
    assert entry.provider == "openai"
    assert entry.prompt_tokens == 111
    assert entry.completion_tokens == 56


@pytest.mark.asyncio
@respx.mock
async def test_ai_cfo_disabled_skips_providers() -> None:
    anthropic_route = respx.post("https://api.anthropic.com/v1/messages").mock(
        return_value=_anthropic_ok()
    )
    client = AIClient(
        _settings(
            enabled=False,
            anthropic="sk-ant-real",
            openai="sk-openai-real",
            deepseek="sk-deepseek-real",
        )
    )

    with pytest.raises(AIProviderUnavailableError, match="AI CFO is disabled"):
        await client.complete("system", "user")

    assert anthropic_route.called is False
