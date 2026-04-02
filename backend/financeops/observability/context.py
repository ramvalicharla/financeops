from __future__ import annotations

import contextvars
from typing import Optional

_request_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "request_id",
    default=None,
)
_correlation_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "correlation_id",
    default=None,
)
_tenant_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "tenant_id",
    default=None,
)
_org_entity_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "org_entity_id",
    default=None,
)


def set_request_context(
    request_id: str,
    tenant_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    org_entity_id: Optional[str] = None,
) -> None:
    _request_id.set(request_id)
    if correlation_id:
        _correlation_id.set(correlation_id)
    if tenant_id:
        _tenant_id.set(tenant_id)
    if org_entity_id:
        _org_entity_id.set(org_entity_id)


def get_request_id() -> Optional[str]:
    return _request_id.get()


def get_correlation_id() -> Optional[str]:
    return _correlation_id.get()


def get_tenant_id() -> Optional[str]:
    return _tenant_id.get()


def get_org_entity_id() -> Optional[str]:
    return _org_entity_id.get()


def clear_request_context() -> None:
    _request_id.set(None)
    _correlation_id.set(None)
    _tenant_id.set(None)
    _org_entity_id.set(None)
