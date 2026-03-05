from __future__ import annotations

import logging
import time

import httpx

from financeops.config import settings
from financeops.core.exceptions import RateLimitError, AllModelsFailedError
from financeops.llm.providers.base import BaseLLMProvider, LLMRequest, LLMResponse

log = logging.getLogger(__name__)

_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


class GeminiProvider(BaseLLMProvider):
    """Google Gemini provider using httpx async client."""

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or settings.GEMINI_API_KEY

    async def generate(self, request: LLMRequest) -> LLMResponse:
        start = time.monotonic()
        model_path = request.model.replace("gemini-", "models/gemini-")
        url = f"{_BASE_URL}/{model_path}:generateContent?key={self._api_key}"
        body = {
            "contents": [
                {"role": "user", "parts": [{"text": request.prompt}]}
            ],
            "systemInstruction": {"parts": [{"text": request.system_prompt}]},
            "generationConfig": {
                "temperature": request.temperature,
                "maxOutputTokens": request.max_tokens,
            },
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                resp = await client.post(url, json=body)
            except httpx.TimeoutException as exc:
                raise TimeoutError(f"Gemini request timed out: {exc}") from exc

        if resp.status_code == 429:
            raise RateLimitError("Gemini rate limit exceeded")
        if resp.status_code >= 400:
            raise AllModelsFailedError(
                f"Gemini API error {resp.status_code}: {resp.text[:200]}"
            )

        data = resp.json()
        duration_ms = (time.monotonic() - start) * 1000
        candidates = data.get("candidates", [])
        content = ""
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            content = " ".join(p.get("text", "") for p in parts)
        usage = data.get("usageMetadata", {})
        prompt_tokens = usage.get("promptTokenCount", 0)
        completion_tokens = usage.get("candidatesTokenCount", 0)
        log.info(
            "Gemini: model=%s tokens=%d duration_ms=%.1f",
            request.model,
            prompt_tokens + completion_tokens,
            duration_ms,
        )
        return LLMResponse(
            content=content,
            model=request.model,
            provider="google",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            duration_ms=duration_ms,
            raw_response=data,
        )

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{_BASE_URL}/models?key={self._api_key}"
                )
            return resp.status_code < 500
        except Exception:
            return False
