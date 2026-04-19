from __future__ import annotations

import logging
import uuid
from collections.abc import Iterable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

from financeops.core.security import decode_token
from financeops.db.session import tenant_session
from financeops.services.audit_service import log_action

log = logging.getLogger(__name__)

_MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_EXEMPT_PATH_PREFIXES = (
    "/health",
    "/ready",
    "/live",
    "/metrics",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/api/v1/health",
    "/api/v1/auth/",
)


def _is_exempt_path(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in _EXEMPT_PATH_PREFIXES)


def _extract_principal_ids(request: Request) -> tuple[uuid.UUID | None, uuid.UUID | None]:
    tenant_value = getattr(request.state, "tenant_id", None)
    user_value: str | None = None

    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        try:
            payload = decode_token(token)
        except Exception:  # noqa: BLE001
            payload = {}
        tenant_value = tenant_value or payload.get("tenant_id")
        user_value = payload.get("sub")

    tenant_id: uuid.UUID | None = None
    user_id: uuid.UUID | None = None
    try:
        if tenant_value:
            tenant_id = uuid.UUID(str(tenant_value))
    except (TypeError, ValueError):
        tenant_id = None
    try:
        if user_value:
            user_id = uuid.UUID(str(user_value))
    except (TypeError, ValueError):
        user_id = None
    return tenant_id, user_id


def _resource_type_from_path(path: str) -> str:
    stripped = path.strip("/")
    if not stripped:
        return "root"
    segments = stripped.split("/")
    if len(segments) >= 3 and segments[0] == "api" and segments[1] == "v1":
        return segments[2]
    return segments[0]


def _resource_id_from_request(request: Request) -> str | None:
    path_params = getattr(request, "path_params", {}) or {}
    values: Iterable[object] = path_params.values()
    for value in values:
        if value is None:
            continue
        return str(value)
    return None


class AuditMiddleware(BaseHTTPMiddleware):
    """
    Write audit trail entries for successful mutating HTTP requests.

    Fail closed on logging errors: responses must still be returned even if the
    audit insert itself fails.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)

        method = request.method.upper()
        path = request.url.path
        if method not in _MUTATING_METHODS:
            return response
        if response.status_code >= 400:
            return response
        if _is_exempt_path(path):
            return response

        tenant_id, user_id = _extract_principal_ids(request)
        if tenant_id is None:
            return response

        try:
            async with tenant_session(tenant_id) as session:
                await log_action(
                    session,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    action=f"http.{method.lower()}",
                    resource_type=_resource_type_from_path(path),
                    resource_id=_resource_id_from_request(request),
                    resource_name=path,
                    ip_address=request.client.host if request.client else None,
                    user_agent=request.headers.get("user-agent"),
                )
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "audit_middleware_write_failed path=%s method=%s error=%s",
                path,
                method,
                exc,
            )

        return response
