from __future__ import annotations

import hashlib
import logging
import time
import uuid

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp
from starlette_csrf import CSRFMiddleware as _BaseCSRFMiddleware

from financeops.core.security import decode_token
from financeops.core.exceptions import AuthenticationError

log = logging.getLogger(__name__)

_RLS_SKIP_PREFIXES = (
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/metrics",
    "/api/v1/auth/",
)


class FinanceOpsCSRFMiddleware(_BaseCSRFMiddleware):
    """
    Preserve upstream CSRF behavior while logging real API bypass paths.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if any(pattern.match(request.url.path) for pattern in self.exempt_urls):
            log.info("CSRF bypass for API route: %s", request.url.path)
        return await super().dispatch(request, call_next)


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """
    Generates a UUID correlation_id per request.
    Attaches it to request.state and response headers.
    """
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        correlation_id = str(uuid.uuid4())
        request.state.correlation_id = correlation_id
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        return response


class RLSMiddleware(BaseHTTPMiddleware):
    """
    Extracts tenant_id from JWT and injects it into request.state.
    The actual PostgreSQL SET CONFIG is done per-session in deps.py
    so that it is tied to the DB session lifetime.
    Skips auth routes and health endpoints.
    """
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path
        skip = any(path.startswith(prefix) for prefix in _RLS_SKIP_PREFIXES)

        if not skip:
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]
                try:
                    payload = decode_token(token)
                    tenant_id = payload.get("tenant_id", "")
                    request.state.tenant_id = tenant_id
                except AuthenticationError:
                    request.state.tenant_id = ""
            else:
                request.state.tenant_id = ""
        else:
            request.state.tenant_id = ""

        return await call_next(request)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Logs method, path, status, duration, and a hash of tenant_id.
    Never logs raw tenant IDs or request bodies for auth routes.
    """
    _AUTH_PATHS = ("/api/v1/auth/login", "/api/v1/auth/register", "/api/v1/auth/mfa")

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)

        tenant_id_raw = getattr(request.state, "tenant_id", "")
        tenant_id_hash = (
            hashlib.sha256(tenant_id_raw.encode()).hexdigest()[:12]
            if tenant_id_raw
            else "anonymous"
        )
        correlation_id = getattr(request.state, "correlation_id", "unknown")

        log.info(
            "%s %s %d %.2fms tenant=%s corr=%s",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            tenant_id_hash,
            correlation_id,
        )
        return response
