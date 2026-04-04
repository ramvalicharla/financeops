from __future__ import annotations

from typing import Any

from financeops.observability.context import get_correlation_id


def current_correlation_id(default: str | None = None) -> str | None:
    """
    Return the current correlation id from request/task context, if available.
    """
    return get_correlation_id() or default


def inject_correlation(
    kwargs: dict[str, Any] | None,
    *,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    """
    Return a kwargs dict enriched with `correlation_id` if absent.
    This is intentionally additive and does not mutate the input object.
    """
    payload: dict[str, Any] = dict(kwargs or {})
    if "correlation_id" in payload and payload["correlation_id"]:
        return payload
    resolved = correlation_id or current_correlation_id()
    if resolved:
        payload["correlation_id"] = str(resolved)
    return payload

