from __future__ import annotations

import contextvars
from typing import Optional

_request_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "request_id",
    default=None,
)
_tenant_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "tenant_id",
    default=None,
)


def set_request_context(request_id: str, tenant_id: Optional[str] = None) -> None:
    _request_id.set(request_id)
    if tenant_id:
        _tenant_id.set(tenant_id)


def get_request_id() -> Optional[str]:
    return _request_id.get()


def get_tenant_id() -> Optional[str]:
    return _tenant_id.get()


def clear_request_context() -> None:
    _request_id.set(None)
    _tenant_id.set(None)

