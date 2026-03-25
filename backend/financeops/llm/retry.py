from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass, field
from decimal import Decimal
from typing import TypeVar

from financeops.core.exceptions import AllModelsFailedError, RateLimitError

T = TypeVar("T")


@dataclass(slots=True)
class RetryConfig:
    max_attempts: int = 3
    base_delay_ms: int = 500
    max_delay_ms: int = 30_000
    jitter_pct: Decimal = Decimal("0.25")
    retryable_status_codes: set[int] = field(
        default_factory=lambda: {429, 500, 502, 503, 504},
    )


def _compute_delay(
    attempt: int,
    config: RetryConfig,
    retry_after_ms: int = 0,
) -> int:
    if retry_after_ms > 0:
        base = retry_after_ms
    else:
        base = min(config.base_delay_ms * (2**attempt), config.max_delay_ms)
    jitter_range = int(base * float(config.jitter_pct))
    if jitter_range <= 0:
        return base
    return base + random.randint(-jitter_range, jitter_range)


def _retry_after_ms(exc: Exception) -> int:
    value = getattr(exc, "retry_after_ms", 0)
    try:
        return int(value)
    except Exception:
        return 0


def _status_code(exc: Exception) -> int:
    value = getattr(exc, "status_code", 0)
    try:
        return int(value)
    except Exception:
        return 0


def _is_retryable(exc: Exception, config: RetryConfig) -> bool:
    if isinstance(exc, RateLimitError | asyncio.TimeoutError):
        return True
    status_code = _status_code(exc)
    if status_code and status_code in config.retryable_status_codes:
        return True
    return isinstance(exc, AllModelsFailedError)


async def with_retry(
    func,  # type: ignore[no-untyped-def]
    config: RetryConfig | None = None,
    *args,  # type: ignore[no-untyped-def]
    **kwargs,  # type: ignore[no-untyped-def]
) -> T:
    retry_config = config or RetryConfig()
    last_exc: Exception | None = None

    for attempt in range(retry_config.max_attempts):
        try:
            return await func(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001
            if not _is_retryable(exc, retry_config):
                raise
            last_exc = exc
            if attempt >= retry_config.max_attempts - 1:
                break
            delay_ms = _compute_delay(
                attempt=attempt,
                config=retry_config,
                retry_after_ms=_retry_after_ms(exc),
            )
            await asyncio.sleep(delay_ms / 1000)

    if last_exc is not None:
        raise last_exc
    raise RuntimeError("Retry wrapper reached an invalid state")


__all__ = ["RetryConfig", "with_retry"]
