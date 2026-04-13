from __future__ import annotations

import asyncio
import logging
import uuid

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp
from starlette_csrf import CSRFMiddleware as _BaseCSRFMiddleware

from financeops.core.security import decode_token
from financeops.core.exceptions import AuthenticationError
from financeops.config import settings

log = logging.getLogger(__name__)

_RLS_SKIP_PREFIXES = (
    "/health",
    "/ready",
    "/live",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/metrics",
    "/api/v1/auth/",
)
_BODY_METHODS = {"POST", "PUT", "PATCH"}
_REQUEST_SIZE_BYPASS_PREFIXES = (
    "/health",
    "/ready",
    "/live",
    "/metrics",
    "/docs",
    "/redoc",
    "/openapi.json",
)
_REQUEST_TIMEOUT_BYPASS_PREFIXES = (
    "/api/v1/ai/stream",
    "/api/v1/notifications/stream",
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
        correlation_id = (
            request.headers.get("X-Correlation-ID")
            or getattr(request.state, "correlation_id", None)
            or str(uuid.uuid4())
        )
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
    Legacy middleware kept in chain order for compatibility.
    Request logging is handled centrally by observability.LoggingMiddleware.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        return await call_next(request)


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """
    Fail closed on oversized request bodies using Content-Length.
    """

    def __init__(self, app: ASGIApp, max_bytes: int | None = None) -> None:
        super().__init__(app)
        self.max_bytes = max_bytes or int(settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method.upper() not in _BODY_METHODS:
            return await call_next(request)
        if any(request.url.path.startswith(prefix) for prefix in _REQUEST_SIZE_BYPASS_PREFIXES):
            return await call_next(request)
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                requested = int(content_length)
            except ValueError:
                requested = 0
            if requested > self.max_bytes:
                log.warning(
                    "Rejected oversized request path=%s content_length=%s max_bytes=%s",
                    request.url.path,
                    requested,
                    self.max_bytes,
                )
                return JSONResponse(
                    status_code=413,
                    content={"error": "payload_too_large", "message": "Request payload exceeds allowed size"},
                )
        return await call_next(request)


class RequestTimeoutMiddleware(BaseHTTPMiddleware):
    """
    Bound request handling time for non-streaming endpoints.
    """

    def __init__(self, app: ASGIApp, timeout_seconds: float = 30.0) -> None:
        super().__init__(app)
        self.timeout_seconds = timeout_seconds

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if any(request.url.path.startswith(prefix) for prefix in _REQUEST_TIMEOUT_BYPASS_PREFIXES):
            return await call_next(request)
        try:
            return await asyncio.wait_for(call_next(request), timeout=self.timeout_seconds)
        except asyncio.TimeoutError:
            log.warning(
                "Rejected timed out request path=%s timeout_seconds=%s",
                request.url.path,
                self.timeout_seconds,
            )
            return JSONResponse(
                status_code=504,
                content={
                    "error": "request_timeout",
                    "message": "Request exceeded allowed processing time",
                },
            )
