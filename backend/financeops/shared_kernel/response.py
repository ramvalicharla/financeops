from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Generic, TypeVar

from fastapi import Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

T = TypeVar("T")

_ENVELOPE_SKIP_PREFIXES = (
    "/docs",
    "/redoc",
    "/openapi.json",
    "/metrics",
)


class Meta(BaseModel):
    request_id: str
    timestamp: datetime
    api_version: str = "1.0"


class ErrorDetail(BaseModel):
    code: str
    message: str
    field: str | None = None
    details: Any | None = None


class ApiResponse(BaseModel, Generic[T]):
    success: bool
    data: T | None = None
    error: ErrorDetail | None = None
    meta: Meta


def ok(data: T, request_id: str | None = None) -> ApiResponse[T]:
    return ApiResponse(
        success=True,
        data=data,
        error=None,
        meta=Meta(
            request_id=request_id or str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc),
        ),
    )


def err(
    code: str,
    message: str,
    field: str | None = None,
    details: Any | None = None,
    request_id: str | None = None,
) -> ApiResponse[None]:
    return ApiResponse(
        success=False,
        data=None,
        error=ErrorDetail(code=code, message=message, field=field, details=details),
        meta=Meta(
            request_id=request_id or str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc),
        ),
    )


class RequestIDMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        billing_warning = getattr(request.state, "billing_warning", None)
        if billing_warning:
            response.headers["X-Billing-Warning"] = str(billing_warning)
        return response


class ApiResponseEnvelopeMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)

        if any(request.url.path.startswith(prefix) for prefix in _ENVELOPE_SKIP_PREFIXES):
            return response

        content_type = response.headers.get("content-type", "").lower()
        if "application/json" not in content_type:
            return response

        body = b""
        async for chunk in response.body_iterator:
            body += chunk

        if not body:
            return self._rebuild_response(response, body)

        try:
            payload = json.loads(body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return self._rebuild_response(response, body)

        if self._is_enveloped(payload):
            return self._json_response(response, payload)

        request_id = getattr(request.state, "request_id", None)
        if response.status_code >= 400:
            wrapped = self._wrap_error_payload(payload, response.status_code, request_id)
        else:
            wrapped = ok(payload, request_id=request_id).model_dump(mode="json")
        return self._json_response(response, wrapped)

    @staticmethod
    def _is_enveloped(payload: Any) -> bool:
        return (
            isinstance(payload, dict)
            and "success" in payload
            and "meta" in payload
            and ("data" in payload or "error" in payload)
        )

    @staticmethod
    def _extract_error_field(detail: Any) -> str | None:
        if not isinstance(detail, list) or not detail:
            return None
        first = detail[0]
        if not isinstance(first, dict):
            return None
        loc = first.get("loc")
        if isinstance(loc, list) and loc:
            return ".".join(str(item) for item in loc if item != "body")
        return None

    def _wrap_error_payload(
        self,
        payload: Any,
        status_code: int,
        request_id: str | None,
    ) -> dict[str, Any]:
        code = f"http_{status_code}"
        message: Any = "Request failed"
        field: str | None = None

        if isinstance(payload, dict):
            if "error" in payload and isinstance(payload["error"], str):
                code = payload["error"]
            elif "code" in payload and isinstance(payload["code"], str):
                code = payload["code"]

            if "message" in payload:
                message = payload["message"]
            elif "detail" in payload:
                message = payload["detail"]
                field = self._extract_error_field(payload["detail"])
            elif "error" in payload and isinstance(payload["error"], str):
                message = payload["error"]
        else:
            message = payload

        if isinstance(message, list):
            message = "Validation failed"
        message_str = str(message)
        return err(code, message_str, field=field, request_id=request_id).model_dump(mode="json")

    @staticmethod
    def _json_response(response: Response, payload: Any) -> JSONResponse:
        wrapped = JSONResponse(
            status_code=response.status_code,
            content=payload,
            background=response.background,
        )
        for key, value in response.raw_headers:
            lower_key = key.decode("latin-1").lower()
            if lower_key in {"content-length", "content-type"}:
                continue
            wrapped.raw_headers.append((key, value))
        return wrapped

    @staticmethod
    def _rebuild_response(response: Response, body: bytes) -> Response:
        rebuilt = Response(
            content=body,
            status_code=response.status_code,
            media_type=response.media_type,
            background=response.background,
        )
        for key, value in response.raw_headers:
            lower_key = key.decode("latin-1").lower()
            if lower_key in {"content-length", "content-type"}:
                continue
            rebuilt.raw_headers.append((key, value))
        return rebuilt
