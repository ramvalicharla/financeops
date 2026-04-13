from __future__ import annotations

import logging
import time
from collections.abc import AsyncGenerator

from financeops.config import settings
from financeops.core.exceptions import RateLimitError, AllModelsFailedError
from financeops.llm.providers.base import BaseLLMProvider, LLMRequest, LLMResponse

log = logging.getLogger(__name__)


class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude provider using the official anthropic SDK."""

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or settings.ANTHROPIC_API_KEY

    def _client(self):
        from anthropic import AsyncAnthropic
        return AsyncAnthropic(api_key=self._api_key)

    async def generate(self, request: LLMRequest) -> LLMResponse:
        start = time.monotonic()
        from anthropic import RateLimitError as AnthropicRateLimitError, APIStatusError

        try:
            async with self._client() as client:
                message = await client.messages.create(
                    model=request.model,
                    max_tokens=request.max_tokens,
                    temperature=request.temperature,
                    system=request.system_prompt,
                    messages=[{"role": "user", "content": request.prompt}],
                )
        except AnthropicRateLimitError as exc:
            raise RateLimitError("Anthropic rate limit exceeded") from exc
        except APIStatusError as exc:
            raise AllModelsFailedError(
                f"Anthropic API error {exc.status_code}: {str(exc)[:200]}"
            ) from exc

        duration_ms = (time.monotonic() - start) * 1000
        content = " ".join(
            block.text for block in message.content if hasattr(block, "text")
        )
        prompt_tokens = message.usage.input_tokens
        completion_tokens = message.usage.output_tokens
        log.info(
            "Anthropic: model=%s tokens=%d duration_ms=%.1f",
            request.model,
            prompt_tokens + completion_tokens,
            duration_ms,
        )
        return LLMResponse(
            content=content,
            model=request.model,
            provider="anthropic",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            duration_ms=duration_ms,
            raw_response={},
        )

    async def stream_complete(self, request: LLMRequest) -> AsyncGenerator[str, None]:
        from anthropic import RateLimitError as AnthropicRateLimitError, APIStatusError

        try:
            async with self._client() as client:
                async with client.messages.stream(
                    model=request.model,
                    max_tokens=request.max_tokens,
                    temperature=request.temperature,
                    system=request.system_prompt,
                    messages=[{"role": "user", "content": request.prompt}],
                ) as stream:
                    async for text in stream.text_stream:
                        yield text
        except AnthropicRateLimitError as exc:
            raise RateLimitError("Anthropic rate limit exceeded") from exc
        except APIStatusError as exc:
            raise AllModelsFailedError(
                f"Anthropic API error {exc.status_code}: {str(exc)[:200]}"
            ) from exc

    async def health_check(self) -> bool:
        try:
            async with self._client() as client:
                await client.models.list()
            return True
        except Exception:
            return False
