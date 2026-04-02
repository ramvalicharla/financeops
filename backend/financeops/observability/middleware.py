from __future__ import annotations

import logging
import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from financeops.observability.business_metrics import (
    api_error_counter,
    api_request_counter,
    api_request_latency_ms,
)
from financeops.observability.context import clear_request_context, set_request_context

log = logging.getLogger(__name__)


def _route_template(request: Request) -> str:
    route = request.scope.get("route")
    route_path = getattr(route, "path", None)
    if isinstance(route_path, str) and route_path:
        return route_path
    return request.url.path


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        request_id = (
            request.headers.get("X-Request-ID")
            or getattr(request.state, "request_id", None)
            or str(uuid.uuid4())
        )
        correlation_id = (
            request.headers.get("X-Correlation-ID")
            or getattr(request.state, "correlation_id", None)
            or request_id
        )
        tenant_id = (
            getattr(request.state, "tenant_id", None)
            or request.headers.get("X-Tenant-ID")
        )
        org_entity_id = (
            getattr(request.state, "org_entity_id", None)
            or request.headers.get("X-Entity-ID")
        )

        request.state.request_id = request_id
        request.state.correlation_id = correlation_id

        set_request_context(
            request_id=request_id,
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            org_entity_id=org_entity_id,
        )

        started_at = time.perf_counter()
        log.info(
            "request_start",
            extra={
                "event": "request_start",
                "method": request.method,
                "path": request.url.path,
                "request_id": request_id,
                "correlation_id": correlation_id,
                "tenant_id": tenant_id,
                "org_entity_id": org_entity_id,
            },
        )

        try:
            response = await call_next(request)
        except Exception:
            elapsed_ms = (time.perf_counter() - started_at) * 1000
            route_path = _route_template(request)
            api_request_counter.labels(
                method=request.method,
                path=route_path,
                status_code="500",
            ).inc()
            api_error_counter.labels(
                method=request.method,
                path=route_path,
                status_code="500",
            ).inc()
            api_request_latency_ms.labels(
                method=request.method,
                path=route_path,
            ).observe(elapsed_ms)
            log.exception(
                "request_error",
                extra={
                    "event": "request_error",
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": round(elapsed_ms, 2),
                    "request_id": request_id,
                    "correlation_id": correlation_id,
                    "tenant_id": tenant_id,
                    "org_entity_id": org_entity_id,
                },
            )
            clear_request_context()
            raise

        elapsed_ms = (time.perf_counter() - started_at) * 1000
        route_path = _route_template(request)
        status_code = str(response.status_code)
        api_request_counter.labels(
            method=request.method,
            path=route_path,
            status_code=status_code,
        ).inc()
        if response.status_code >= 400:
            api_error_counter.labels(
                method=request.method,
                path=route_path,
                status_code=status_code,
            ).inc()
        api_request_latency_ms.labels(
            method=request.method,
            path=route_path,
        ).observe(elapsed_ms)
        log.info(
            "request_end",
            extra={
                "event": "request_end",
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round(elapsed_ms, 2),
                "request_id": request_id,
                "correlation_id": correlation_id,
                "tenant_id": getattr(request.state, "tenant_id", tenant_id),
                "org_entity_id": org_entity_id,
            },
        )
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Correlation-ID"] = correlation_id
        clear_request_context()
        return response
