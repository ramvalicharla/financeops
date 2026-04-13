from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

MODEL_CONTEXT_LIMITS: dict[str, int] = {
    "claude-opus-4-5-20251001": 200_000,
    "claude-sonnet-4-5-20251001": 200_000,
    "claude-haiku-4-5-20251001": 200_000,
    "gpt-4o": 128_000,
    "gpt-4o-mini": 128_000,
    "gemini-1.5-pro": 1_000_000,
    "gemini-1.5-flash": 1_000_000,
    "mistral:7b": 32_000,
    "phi3:mini": 128_000,
}

RESPONSE_RESERVE = 4_000


@dataclass(slots=True)
class TokenBudget:
    model: str
    context_limit: int
    response_reserve: int
    available_for_prompt: int
    system_tokens: int
    user_tokens: int
    truncated: bool
    truncation_pct: Decimal
    truncated_user_prompt: str


def compute_token_budget(
    model: str,
    system_prompt: str,
    user_prompt: str,
    encoding: str = "cl100k_base",
) -> TokenBudget:
    try:
        import tiktoken  # type: ignore

        enc = tiktoken.get_encoding(encoding)

        def count_tokens(text: str) -> int:
            return len(enc.encode(text))

    except Exception:

        def count_tokens(text: str) -> int:
            return max(len(text) // 4, 0)

    limit = MODEL_CONTEXT_LIMITS.get(model, 32_000)
    available = max(limit - RESPONSE_RESERVE, 0)
    system_tokens = count_tokens(system_prompt)
    user_tokens = count_tokens(user_prompt)
    total = system_tokens + user_tokens
    truncated = False
    truncated_user_prompt = user_prompt

    if total > available:
        user_budget = available - system_tokens
        if user_budget <= 0:
            truncated_user_prompt = ""
            user_tokens = 0
        else:
            chars_per_token = len(user_prompt) / max(user_tokens, 1)
            truncate_at = max(int(user_budget * chars_per_token), 0)
            truncated_user_prompt = user_prompt[:truncate_at]
            user_tokens = count_tokens(truncated_user_prompt)
        truncated = True

    used = system_tokens + user_tokens
    if total <= 0:
        truncation_pct = Decimal("0")
    else:
        truncation_pct = Decimal(str(round((1 - (used / total)) * 100, 2)))

    return TokenBudget(
        model=model,
        context_limit=limit,
        response_reserve=RESPONSE_RESERVE,
        available_for_prompt=available,
        system_tokens=system_tokens,
        user_tokens=user_tokens,
        truncated=truncated,
        truncation_pct=truncation_pct,
        truncated_user_prompt=truncated_user_prompt,
    )


__all__ = [
    "MODEL_CONTEXT_LIMITS",
    "RESPONSE_RESERVE",
    "TokenBudget",
    "compute_token_budget",
]
