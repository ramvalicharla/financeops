from __future__ import annotations

import logging
import time

import httpx

from financeops.config import settings
from financeops.core.exceptions import RateLimitError, AllModelsFailedError
from financeops.llm.providers.base import BaseLLMProvider, LLMRequest, LLMResponse

log = logging.getLogger(__name__)

_BASE_URL = "https://api.anthropic.com"
_API_VERSION = "2023-06-01"


class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude provider using httpx async client."""

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or settings.ANTHROPIC_API_KEY

    async def generate(self, request: LLMRequest) -> LLMResponse:
        start = time.monotonic()
        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": _API_VERSION,
            "content-type": "application/json",
        }
        body = {
            "model": request.model,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "system": request.system_prompt,
            "messages": [{"role": "user", "content": request.prompt}],
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                resp = await client.post(
                    f"{_BASE_URL}/v1/messages",
                    json=body,
                    headers=headers,
                )
            except httpx.TimeoutException as exc:
                raise TimeoutError(f"Anthropic request timed out: {exc}") from exc

        if resp.status_code == 429:
            raise RateLimitError("Anthropic rate limit exceeded")
        if resp.status_code >= 400:
            raise AllModelsFailedError(
                f"Anthropic API error {resp.status_code}: {resp.text[:200]}"
            )

        data = resp.json()
        duration_ms = (time.monotonic() - start) * 1000
        usage = data.get("usage", {})
        content_blocks = data.get("content", [])
        content = " ".join(
            block.get("text", "") for block in content_blocks if block.get("type") == "text"
        )
        log.info(
            "Anthropic: model=%s tokens=%d duration_ms=%.1f",
            request.model,
            usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
            duration_ms,
        )
        return LLMResponse(
            content=content,
            model=request.model,
            provider="anthropic",
            prompt_tokens=usage.get("input_tokens", 0),
            completion_tokens=usage.get("output_tokens", 0),
            total_tokens=usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
            duration_ms=duration_ms,
            raw_response=data,
        )

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{_BASE_URL}/v1/models",
                    headers={
                        "x-api-key": self._api_key,
                        "anthropic-version": _API_VERSION,
                    },
                )
            return resp.status_code < 500
        except Exception:
            return False
