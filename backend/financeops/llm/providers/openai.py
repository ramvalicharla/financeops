from __future__ import annotations

import logging
import time
from collections.abc import AsyncGenerator

import httpx

from financeops.config import settings
from financeops.core.exceptions import RateLimitError, AllModelsFailedError
from financeops.llm.providers.base import BaseLLMProvider, LLMRequest, LLMResponse

log = logging.getLogger(__name__)

_BASE_URL = "https://api.openai.com/v1"


class OpenAIProvider(BaseLLMProvider):
    """OpenAI provider using httpx async client."""

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or settings.OPENAI_API_KEY

    async def generate(self, request: LLMRequest) -> LLMResponse:
        start = time.monotonic()
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": request.model,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.prompt},
            ],
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                resp = await client.post(
                    f"{_BASE_URL}/chat/completions",
                    json=body,
                    headers=headers,
                )
            except httpx.TimeoutException as exc:
                raise TimeoutError(f"OpenAI request timed out: {exc}") from exc

        if resp.status_code == 429:
            raise RateLimitError("OpenAI rate limit exceeded")
        if resp.status_code >= 400:
            raise AllModelsFailedError(
                f"OpenAI API error {resp.status_code}: {resp.text[:200]}"
            )

        data = resp.json()
        duration_ms = (time.monotonic() - start) * 1000
        usage = data.get("usage", {})
        choices = data.get("choices", [])
        content = choices[0]["message"]["content"] if choices else ""
        log.info(
            "OpenAI: model=%s tokens=%d duration_ms=%.1f",
            request.model,
            usage.get("total_tokens", 0),
            duration_ms,
        )
        return LLMResponse(
            content=content,
            model=request.model,
            provider="openai",
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            duration_ms=duration_ms,
            raw_response=data,
        )

    async def stream_complete(self, request: LLMRequest) -> AsyncGenerator[str, None]:
        """
        Lightweight streaming adapter.
        Uses regular completion and yields chunked text when SSE streaming is unavailable.
        """
        response = await self.generate(request)
        for token in response.content.split():
            yield f"{token} "

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{_BASE_URL}/models",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                )
            return resp.status_code < 500
        except Exception:
            return False
