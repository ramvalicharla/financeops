from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import Any


@dataclass
class LLMRequest:
    prompt: str
    system_prompt: str
    model: str
    temperature: float = 0.2
    max_tokens: int = 4096
    tenant_id: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMResponse:
    content: str
    model: str
    provider: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    duration_ms: float
    raw_response: dict[str, Any] = field(default_factory=dict)


class BaseLLMProvider(ABC):
    """Abstract base class for all LLM providers."""

    @abstractmethod
    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate a response from the LLM."""
        ...

    async def stream_complete(self, request: LLMRequest) -> AsyncGenerator[str, None]:
        """
        Default streaming implementation: fallback to single-shot generation.
        Provider adapters can override with true token streaming.
        """
        response = await self.generate(request)
        yield response.content

    @abstractmethod
    async def health_check(self) -> bool:
        """Return True if the provider is reachable and healthy."""
        ...
