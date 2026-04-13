from __future__ import annotations

import logging
import time
from collections.abc import AsyncGenerator

from financeops.config import settings
from financeops.core.exceptions import AllModelsFailedError
from financeops.llm.providers.base import BaseLLMProvider, LLMRequest, LLMResponse

log = logging.getLogger(__name__)


class OllamaProvider(BaseLLMProvider):
    """Ollama local LLM provider using the official ollama SDK."""

    def __init__(self, base_url: str | None = None) -> None:
        self._base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")

    def _client(self):
        from ollama import AsyncClient
        return AsyncClient(host=self._base_url)

    async def generate(self, request: LLMRequest) -> LLMResponse:
        start = time.monotonic()
        try:
            client = self._client()
            response = await client.generate(
                model=request.model,
                prompt=f"{request.system_prompt}\n\n{request.prompt}",
                options={
                    "temperature": request.temperature,
                    "num_predict": request.max_tokens,
                },
            )
        except Exception as exc:
            raise AllModelsFailedError(f"Ollama error: {exc}") from exc

        duration_ms = (time.monotonic() - start) * 1000
        content = response.response if hasattr(response, "response") else str(response)
        prompt_tokens = getattr(response, "prompt_eval_count", 0) or 0
        completion_tokens = getattr(response, "eval_count", 0) or 0
        log.info(
            "Ollama: model=%s tokens=%d duration_ms=%.1f",
            request.model,
            prompt_tokens + completion_tokens,
            duration_ms,
        )
        return LLMResponse(
            content=content,
            model=request.model,
            provider="ollama",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            duration_ms=duration_ms,
            raw_response={},
        )

    async def stream_complete(self, request: LLMRequest) -> AsyncGenerator[str, None]:
        try:
            client = self._client()
            async for chunk in await client.generate(
                model=request.model,
                prompt=f"{request.system_prompt}\n\n{request.prompt}",
                options={
                    "temperature": request.temperature,
                    "num_predict": request.max_tokens,
                },
                stream=True,
            ):
                text = chunk.response if hasattr(chunk, "response") else ""
                if text:
                    yield text
        except Exception as exc:
            raise AllModelsFailedError(f"Ollama stream error: {exc}") from exc

    async def health_check(self) -> bool:
        try:
            client = self._client()
            await client.list()
            return True
        except Exception:
            return False
