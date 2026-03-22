from __future__ import annotations

import logging
import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from financeops.observability.context import (
    clear_request_context,
    set_request_context,
)

log = logging.getLogger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        tenant_id = request.headers.get("X-Tenant-ID")
        request.state.request_id = request_id
        set_request_context(request_id=request_id, tenant_id=tenant_id)

        started_at = time.perf_counter()
        log.info(
            "request_start",
            extra={
                "method": request.method,
                "path": request.url.path,
                "request_id": request_id,
                "tenant_id": tenant_id,
            },
        )

        try:
            response = await call_next(request)
        except Exception:
            elapsed_ms = (time.perf_counter() - started_at) * 1000
            log.exception(
                "request_error",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": round(elapsed_ms, 2),
                    "request_id": request_id,
                    "tenant_id": tenant_id,
                },
            )
            clear_request_context()
            raise

        elapsed_ms = (time.perf_counter() - started_at) * 1000
        log.info(
            "request_end",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round(elapsed_ms, 2),
                "request_id": request_id,
                "tenant_id": tenant_id,
            },
        )
        clear_request_context()
        return response

