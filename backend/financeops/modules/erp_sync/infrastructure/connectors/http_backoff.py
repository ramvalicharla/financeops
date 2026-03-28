from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import Awaitable, Callable

import httpx

logger = logging.getLogger(__name__)

DEFAULT_MAX_RETRIES = 5
DEFAULT_BASE_DELAY_SECONDS = 1.0
DEFAULT_MAX_DELAY_SECONDS = 60.0
RETRY_AFTER_HEADER = "Retry-After"

_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})
_HARD_FAILURE_STATUS = frozenset({400, 401, 403, 404, 422})


class RateLimitError(Exception):
    def __init__(self, status_code: int, attempts: int) -> None:
        self.status_code = status_code
        self.attempts = attempts
        super().__init__(
            f"Rate limit exceeded after {attempts} attempts (last status: {status_code})"
        )


class TransientError(Exception):
    def __init__(self, status_code: int, attempts: int) -> None:
        self.status_code = status_code
        self.attempts = attempts
        super().__init__(
            f"Transient error after {attempts} attempts (last status: {status_code})"
        )


def _compute_delay(
    attempt: int,
    base_delay: float,
    max_delay: float,
    retry_after: float | None,
) -> float:
    if retry_after is not None:
        return min(retry_after, max_delay)

    exp_delay = min(base_delay * (2**attempt), max_delay)
    jitter = random.uniform(0.0, exp_delay)
    return min(exp_delay + jitter, max_delay)


def _parse_retry_after(response: httpx.Response) -> float | None:
    value = response.headers.get(RETRY_AFTER_HEADER)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


async def with_backoff(
    fn: Callable[[], Awaitable[httpx.Response]],
    *,
    max_retries: int = DEFAULT_MAX_RETRIES,
    base_delay: float = DEFAULT_BASE_DELAY_SECONDS,
    max_delay: float = DEFAULT_MAX_DELAY_SECONDS,
    context: str = "",
) -> httpx.Response:
    last_status = 0
    attempts = max_retries + 1

    for attempt in range(attempts):
        response = await fn()
        last_status = response.status_code

        if response.status_code < 400:
            if attempt > 0:
                logger.info("http_backoff_success_after_retry attempt=%d context=%s", attempt, context)
            return response

        if response.status_code in _HARD_FAILURE_STATUS:
            logger.warning(
                "http_backoff_hard_failure status=%d context=%s",
                response.status_code,
                context,
            )
            return response

        if response.status_code in _RETRYABLE_STATUS:
            if attempt >= max_retries:
                break
            retry_after = _parse_retry_after(response)
            delay = _compute_delay(attempt, base_delay, max_delay, retry_after)
            logger.warning(
                "http_backoff_retry status=%d attempt=%d max_retries=%d delay=%.2f context=%s",
                response.status_code,
                attempt + 1,
                max_retries,
                delay,
                context,
            )
            await asyncio.sleep(delay)
            continue

        return response

    if last_status == 429:
        raise RateLimitError(last_status, attempts)
    raise TransientError(last_status, attempts)

