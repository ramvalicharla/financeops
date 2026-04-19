from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.llm.cost_ledger import compute_cost
from financeops.db.models.ai_cfo_layer import AiCfoLedger
from financeops.modules.ai_cfo_layer.domain.exceptions import AIProviderUnavailableError

log = logging.getLogger(__name__)


@dataclass(slots=True)
class AIResponse:
    text: str
    provider_used: str
    model_used: str
    prompt_tokens: int
    completion_tokens: int


class AIProvider(Protocol):
    name: str
    model: str

    async def complete(
        self,
        system: str,
        user: str,
        max_tokens: int = 1000,
    ) -> AIResponse: ...


class AnthropicProvider:
    name = "anthropic"
    endpoint = "https://api.anthropic.com/v1/messages"
    model = "claude-3-5-haiku-20241022"

    def __init__(self, api_key: str):
        self._api_key = api_key

    async def complete(
        self,
        system: str,
        user: str,
        max_tokens: int = 1000,
    ) -> AIResponse:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                self.endpoint,
                headers={
                    "x-api-key": self._api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": self.model,
                    "max_tokens": max_tokens,
                    "system": system,
                    "messages": [{"role": "user", "content": user}],
                },
            )
            response.raise_for_status()
            payload = response.json()
            return AIResponse(
                text=str(payload["content"][0]["text"]),
                provider_used=self.name,
                model_used=self.model,
                prompt_tokens=int(payload.get("usage", {}).get("input_tokens", 0)),
                completion_tokens=int(payload.get("usage", {}).get("output_tokens", 0)),
            )


class OpenAIProvider:
    name = "openai"
    endpoint = "https://api.openai.com/v1/chat/completions"
    model = "gpt-4o-mini"

    def __init__(self, api_key: str):
        self._api_key = api_key

    async def complete(
        self,
        system: str,
        user: str,
        max_tokens: int = 1000,
    ) -> AIResponse:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                self.endpoint,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "content-type": "application/json",
                },
                json={
                    "model": self.model,
                    "max_completion_tokens": max_tokens,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                },
            )
            response.raise_for_status()
            payload = response.json()
            choice = payload["choices"][0]["message"]["content"]
            return AIResponse(
                text=str(choice),
                provider_used=self.name,
                model_used=self.model,
                prompt_tokens=int(payload.get("usage", {}).get("prompt_tokens", 0)),
                completion_tokens=int(payload.get("usage", {}).get("completion_tokens", 0)),
            )


class DeepSeekProvider:
    name = "deepseek"
    endpoint = "https://api.deepseek.com/v1/chat/completions"
    model = "deepseek-chat"

    def __init__(self, api_key: str):
        self._api_key = api_key

    async def complete(
        self,
        system: str,
        user: str,
        max_tokens: int = 1000,
    ) -> AIResponse:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                self.endpoint,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "content-type": "application/json",
                },
                json={
                    "model": self.model,
                    "max_tokens": max_tokens,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                },
            )
            response.raise_for_status()
            payload = response.json()
            choice = payload["choices"][0]["message"]["content"]
            return AIResponse(
                text=str(choice),
                provider_used=self.name,
                model_used=self.model,
                prompt_tokens=int(payload.get("usage", {}).get("prompt_tokens", 0)),
                completion_tokens=int(payload.get("usage", {}).get("completion_tokens", 0)),
            )


class AIClient:
    """
    Tries providers in priority order and falls back automatically.
    """

    def __init__(self, settings):
        self._enabled = bool(
            getattr(settings, "ai_cfo_enabled", getattr(settings, "AI_CFO_ENABLED", True))
        )
        self.providers = self._build_provider_list(settings)

    def _build_provider_list(self, settings) -> list[AIProvider]:
        providers: list[AIProvider] = []
        if self._is_valid_key(getattr(settings, "anthropic_api_key", None)):
            providers.append(AnthropicProvider(settings.anthropic_api_key))
        if self._is_valid_key(getattr(settings, "openai_api_key", None)):
            providers.append(OpenAIProvider(settings.openai_api_key))
        if self._is_valid_key(getattr(settings, "deepseek_api_key", None)):
            providers.append(DeepSeekProvider(settings.deepseek_api_key))
        return providers

    def _is_valid_key(self, key: str | None) -> bool:
        return bool(key and "PLACEHOLDER" not in key.upper())

    async def complete(
        self,
        system: str,
        user: str,
        max_tokens: int = 1000,
    ) -> AIResponse:
        if not self._enabled:
            raise AIProviderUnavailableError(
                "AI CFO is disabled; provider calls are not permitted"
            )
        if not self.providers:
            raise AIProviderUnavailableError("No AI providers configured")

        last_error: Exception | None = None
        for provider in self.providers:
            try:
                return await provider.complete(system, user, max_tokens)
            except Exception as exc:
                log.warning(
                    "AI provider %s failed: %s. Trying next provider.",
                    provider.name,
                    exc,
                )
                last_error = exc
                continue

        raise AIProviderUnavailableError(
            f"All AI providers failed. Last error: {last_error}"
        )


async def record_ai_cfo_ledger_entry(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    feature: str,
    response: AIResponse,
) -> AiCfoLedger:
    cost_usd: Decimal = compute_cost(
        response.model_used,
        response.prompt_tokens,
        response.completion_tokens,
        provider=response.provider_used,
    )
    entry = AiCfoLedger(
        tenant_id=tenant_id,
        feature=feature,
        provider=response.provider_used,
        model=response.model_used,
        prompt_tokens=response.prompt_tokens,
        completion_tokens=response.completion_tokens,
        cost_usd=cost_usd,
    )
    session.add(entry)
    await session.flush()
    return entry
