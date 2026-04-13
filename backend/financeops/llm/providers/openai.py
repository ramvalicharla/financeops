from __future__ import annotations

import logging
import time
from collections.abc import AsyncGenerator

from financeops.config import settings
from financeops.core.exceptions import RateLimitError, AllModelsFailedError
from financeops.llm.providers.base import BaseLLMProvider, LLMRequest, LLMResponse

log = logging.getLogger(__name__)


class OpenAIProvider(BaseLLMProvider):
    """OpenAI provider using the official openai SDK."""

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or settings.OPENAI_API_KEY

    def _client(self):
        from openai import AsyncOpenAI
        return AsyncOpenAI(api_key=self._api_key)

    async def generate(self, request: LLMRequest) -> LLMResponse:
        start = time.monotonic()
        from openai import RateLimitError as OpenAIRateLimitError, APIStatusError

        try:
            async with self._client() as client:
                completion = await client.chat.completions.create(
                    model=request.model,
                    max_tokens=request.max_tokens,
                    temperature=request.temperature,
                    messages=[
                        {"role": "system", "content": request.system_prompt},
                        {"role": "user", "content": request.prompt},
                    ],
                )
        except OpenAIRateLimitError as exc:
            raise RateLimitError("OpenAI rate limit exceeded") from exc
        except APIStatusError as exc:
            raise AllModelsFailedError(
                f"OpenAI API error {exc.status_code}: {str(exc)[:200]}"
            ) from exc

        duration_ms = (time.monotonic() - start) * 1000
        usage = completion.usage
        content = completion.choices[0].message.content or "" if completion.choices else ""
        prompt_tokens = usage.prompt_tokens if usage else 0
        completion_tokens = usage.completion_tokens if usage else 0
        log.info(
            "OpenAI: model=%s tokens=%d duration_ms=%.1f",
            request.model,
            (prompt_tokens + completion_tokens),
            duration_ms,
        )
        return LLMResponse(
            content=content,
            model=request.model,
            provider="openai",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            duration_ms=duration_ms,
            raw_response={},
        )

    async def stream_complete(self, request: LLMRequest) -> AsyncGenerator[str, None]:
        from openai import RateLimitError as OpenAIRateLimitError, APIStatusError

        try:
            async with self._client() as client:
                async with client.chat.completions.stream(
                    model=request.model,
                    max_tokens=request.max_tokens,
                    temperature=request.temperature,
                    messages=[
                        {"role": "system", "content": request.system_prompt},
                        {"role": "user", "content": request.prompt},
                    ],
                ) as stream:
                    async for event in stream:
                        chunk = event.choices[0].delta.content if event.choices and event.choices[0].delta else None
                        if chunk:
                            yield chunk
        except OpenAIRateLimitError as exc:
            raise RateLimitError("OpenAI rate limit exceeded") from exc
        except APIStatusError as exc:
            raise AllModelsFailedError(
                f"OpenAI API error {exc.status_code}: {str(exc)[:200]}"
            ) from exc

    async def health_check(self) -> bool:
        try:
            async with self._client() as client:
                await client.models.list()
            return True
        except Exception:
            return False
