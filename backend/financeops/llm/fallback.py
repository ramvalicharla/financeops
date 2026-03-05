from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from financeops.core.exceptions import AllModelsFailedError
from financeops.llm.circuit_breaker import CircuitBreakerRegistry
from financeops.llm.providers.base import LLMRequest, LLMResponse

log = logging.getLogger(__name__)


@dataclass
class ModelConfig:
    model_name: str
    provider: str
    timeout: int = 60


@dataclass
class AIResult:
    content: str
    model_used: str
    provider: str
    was_fallback: bool
    attempt_number: int
    duration_ms: float
    tokens_used: int


FALLBACK_CHAINS: dict[str, list[ModelConfig]] = {
    "classification": [
        ModelConfig("phi3:mini", "ollama", timeout=15),
        ModelConfig("mistral:7b", "ollama", timeout=20),
        ModelConfig("claude-haiku-3-5", "anthropic", timeout=30),
        ModelConfig("gpt-4o-mini", "openai", timeout=30),
    ],
    "variance_analysis": [
        ModelConfig("mistral:7b", "ollama", timeout=30),
        ModelConfig("claude-sonnet-4-5", "anthropic", timeout=60),
        ModelConfig("gpt-4o", "openai", timeout=60),
        ModelConfig("gemini-1.5-pro", "google", timeout=60),
    ],
    "advisory": [
        ModelConfig("claude-opus-4-5", "anthropic", timeout=120),
        ModelConfig("gpt-4o", "openai", timeout=120),
        ModelConfig("gemini-1.5-pro", "google", timeout=120),
    ],
    "validation": [
        ModelConfig("gpt-4o-mini", "openai", timeout=30),
        ModelConfig("claude-haiku-3-5", "anthropic", timeout=30),
        ModelConfig("gemini-1.5-flash", "google", timeout=30),
    ],
    "hr_manual": [
        ModelConfig("mistral:7b", "ollama", timeout=30),
        ModelConfig("phi3:mini", "ollama", timeout=20),
        # NO cloud models — HR data stays local only
    ],
}


def _get_provider(provider_name: str, model_name: str):
    """Instantiate the correct provider for a model config."""
    from financeops.llm.providers.anthropic import AnthropicProvider
    from financeops.llm.providers.openai import OpenAIProvider
    from financeops.llm.providers.ollama import OllamaProvider
    from financeops.llm.providers.gemini import GeminiProvider

    match provider_name:
        case "anthropic":
            return AnthropicProvider()
        case "openai":
            return OpenAIProvider()
        case "ollama":
            return OllamaProvider()
        case "google":
            return GeminiProvider()
        case _:
            raise ValueError(f"Unknown provider: {provider_name}")


async def execute_with_fallback(
    *,
    task_type: str,
    prompt: str,
    system_prompt: str,
    tenant_id: str,
    circuit_registry: CircuitBreakerRegistry,
    context: dict | None = None,
) -> AIResult:
    """
    Execute a prompt using the fallback chain for the given task_type.
    Checks circuit breaker before each attempt.
    Raises AllModelsFailedError if all models in the chain fail.
    """
    chain = FALLBACK_CHAINS.get(task_type)
    if not chain:
        raise ValueError(f"Unknown task_type for fallback chain: {task_type}")

    errors: list[str] = []
    for attempt, model_cfg in enumerate(chain):
        model_key = f"{model_cfg.provider}/{model_cfg.model_name}"

        if await circuit_registry.is_open(model_key):
            log.warning("Circuit open for %s — skipping", model_key)
            errors.append(f"{model_key}: circuit open")
            continue

        start = time.monotonic()
        try:
            provider = _get_provider(model_cfg.provider, model_cfg.model_name)
            request = LLMRequest(
                prompt=prompt,
                system_prompt=system_prompt,
                model=model_cfg.model_name,
                tenant_id=tenant_id,
            )
            response: LLMResponse = await provider.generate(request)
            duration_ms = (time.monotonic() - start) * 1000

            await circuit_registry.record_success(model_key)
            log.info(
                "LLM success: task=%s model=%s attempt=%d duration_ms=%.1f",
                task_type,
                model_key,
                attempt + 1,
                duration_ms,
            )
            return AIResult(
                content=response.content,
                model_used=response.model,
                provider=response.provider,
                was_fallback=attempt > 0,
                attempt_number=attempt + 1,
                duration_ms=duration_ms,
                tokens_used=response.total_tokens,
            )
        except Exception as exc:
            await circuit_registry.record_failure(model_key)
            error_msg = f"{model_key}: {type(exc).__name__}: {exc}"
            errors.append(error_msg)
            log.warning("LLM attempt %d failed: %s", attempt + 1, error_msg)

    raise AllModelsFailedError(
        f"All models failed for task '{task_type}': {'; '.join(errors)}"
    )
