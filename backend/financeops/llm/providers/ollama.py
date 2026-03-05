from __future__ import annotations

import logging
import time

import httpx

from financeops.config import settings
from financeops.core.exceptions import AllModelsFailedError
from financeops.llm.providers.base import BaseLLMProvider, LLMRequest, LLMResponse

log = logging.getLogger(__name__)


class OllamaProvider(BaseLLMProvider):
    """Ollama local LLM provider using httpx async client."""

    def __init__(self, base_url: str | None = None) -> None:
        self._base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")

    async def generate(self, request: LLMRequest) -> LLMResponse:
        start = time.monotonic()
        body = {
            "model": request.model,
            "prompt": f"{request.system_prompt}\n\n{request.prompt}",
            "stream": False,
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_tokens,
            },
        }
        async with httpx.AsyncClient(timeout=300.0) as client:
            try:
                resp = await client.post(
                    f"{self._base_url}/api/generate",
                    json=body,
                )
            except httpx.TimeoutException as exc:
                raise TimeoutError(f"Ollama request timed out: {exc}") from exc

        if resp.status_code >= 400:
            raise AllModelsFailedError(
                f"Ollama error {resp.status_code}: {resp.text[:200]}"
            )

        data = resp.json()
        duration_ms = (time.monotonic() - start) * 1000
        content = data.get("response", "")
        prompt_tokens = data.get("prompt_eval_count", 0)
        completion_tokens = data.get("eval_count", 0)
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
            raw_response=data,
        )

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self._base_url}/api/tags")
            return resp.status_code == 200
        except Exception:
            return False
