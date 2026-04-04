from __future__ import annotations

import logging
from typing import Any

from financeops.observability.context import (
    get_correlation_id,
    get_org_entity_id,
    get_request_id,
    get_tenant_id,
)


def log_event(
    logger: logging.Logger,
    event: str,
    *,
    level: int = logging.INFO,
    **fields: Any,
) -> None:
    """
    Emit a structured event with standard request/tenant correlation context.
    Additive helper: callers can progressively adopt without contract changes.
    """
    payload: dict[str, Any] = {
        "event": event,
        "request_id": get_request_id(),
        "correlation_id": get_correlation_id(),
        "tenant_id": get_tenant_id(),
        "org_entity_id": get_org_entity_id(),
    }
    payload.update(fields)
    logger.log(level, event, extra=payload)

