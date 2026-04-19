from __future__ import annotations

import json
import re
from collections.abc import Iterable

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

from financeops.api import deps as api_deps
from financeops.core.security import decode_token
from financeops.shared_kernel.response import err

IDEMPOTENCY_TTL_SECONDS = 86_400
MAX_IDEMPOTENCY_KEY_LENGTH = 128
IDEMPOTENCY_CACHE_PREFIX = "idempotency:"

REQUIRED_ERP_SYNC_ENDPOINT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^/api/v1/erp-sync/sync-runs$"),
    re.compile(r"^/api/v1/erp-sync/publish-events/[^/]+/approve$"),
    re.compile(r"^/api/v1/erp-sync/connections$"),
)

_OPTIONAL_FINANCIAL_POST_PREFIXES: tuple[str, ...] = (
    "/api/v1/coa",
    "/api/v1/billing",
    "/api/v1/mis",
    "/api/v1/normalization",
    "/api/v1/payroll-gl-reconciliation",
    "/api/v1/ratio-variance",
    "/api/v1/financial-risk",
    "/api/v1/anomaly-engine",
    "/api/v1/board-pack",
    "/api/v1/erp-sync",
    "/api/v1/erp-push",
    "/api/v1/reconciliation",
    "/api/v1/recon",
    "/api/v1/bank-recon",
    "/api/v1/fx",
    "/api/v1/consolidation",
    "/api/v1/ownership",
    "/api/v1/cash-flow",
    "/api/v1/equity",
    "/api/v1/observability",
    "/api/v1/revenue",
    "/api/v1/lease",
    "/api/v1/prepaid",
    "/api/v1/fixed-assets",
    "/api/v1/working-capital",
    "/api/v1/gst",
    "/api/v1/monthend",
    "/api/v1/auditor",
    "/api/v1/delivery",
)

_OPTIONAL_IDEMPOTENT_POST_PATHS: tuple[str, ...] = (
    "/api/v1/auth/change-password",
)


def is_required_erp_sync_endpoint(path: str) -> bool:
    return any(pattern.match(path) for pattern in REQUIRED_ERP_SYNC_ENDPOINT_PATTERNS)


def get_idempotency_key(request: Request, *, required: bool = False) -> str | None:
    raw_key = request.headers.get("Idempotency-Key", "")
    key = raw_key.strip()
    if not key:
        if required:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Idempotency-Key header is required",
            )
        return None
    if len(key) > MAX_IDEMPOTENCY_KEY_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Idempotency-Key must be <= {MAX_IDEMPOTENCY_KEY_LENGTH} characters",
        )
    return key


async def require_idempotency_key(request: Request) -> str:
    return get_idempotency_key(request, required=True) or ""


async def optional_idempotency_key(request: Request) -> str | None:
    return get_idempotency_key(request, required=False)


async def require_erp_sync_idempotency_key(request: Request) -> str:
    if not is_required_erp_sync_endpoint(request.url.path):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Required idempotency policy is only valid for ERP sync endpoints",
        )
    return get_idempotency_key(request, required=True) or ""


def _is_financial_post_path(path: str) -> bool:
    return path in _OPTIONAL_IDEMPOTENT_POST_PATHS or any(
        path.startswith(prefix) for prefix in _OPTIONAL_FINANCIAL_POST_PREFIXES
    )


def _extract_tenant_id(request: Request) -> str:
    tenant_id = str(getattr(request.state, "tenant_id", "") or "")
    if tenant_id:
        return tenant_id
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return ""
    token = auth_header[7:]
    try:
        payload = decode_token(token)
    except Exception:
        return ""
    return str(payload.get("tenant_id", "") or "")


def _cache_key(tenant_id: str, idempotency_key: str) -> str:
    return f"{IDEMPOTENCY_CACHE_PREFIX}{tenant_id}:{idempotency_key}"


async def cleanup_nonexpiring_idempotency_keys(redis_client=None) -> int:
    """Delete only malformed idempotency cache keys that were stored without expiry."""
    client = redis_client or api_deps._redis_pool
    if client is None:
        return 0

    removed = 0
    async for raw_key in client.scan_iter(match=f"{IDEMPOTENCY_CACHE_PREFIX}*"):
        key = raw_key.decode("utf-8") if isinstance(raw_key, bytes) else str(raw_key)
        ttl = await client.ttl(key)
        if ttl == -1:
            await client.delete(key)
            removed += 1
    return removed


def _error_response(request: Request, code: str, message: str, *, status_code: int) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    return JSONResponse(
        status_code=status_code,
        content=err(code=code, message=message, request_id=request_id).model_dump(mode="json"),
    )


class IdempotencyMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method.upper() != "POST":
            return await call_next(request)

        path = request.url.path
        if not _is_financial_post_path(path):
            return await call_next(request)
        if "/webhooks/" in path:
            return await call_next(request)

        try:
            key = get_idempotency_key(request, required=False)
        except HTTPException as exc:
            return _error_response(
                request,
                code="invalid_idempotency_key",
                message=str(exc.detail),
                status_code=exc.status_code,
            )

        if key is None:
            return await call_next(request)

        tenant_id = _extract_tenant_id(request)
        if not tenant_id:
            return await call_next(request)

        if api_deps._redis_pool is None:
            return _error_response(
                request,
                code="idempotency_cache_unavailable",
                message="Idempotency cache unavailable",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        redis_key = _cache_key(tenant_id, key)
        cached_body = await api_deps._redis_pool.get(redis_key)
        if cached_body is not None:
            replay = Response(
                content=cached_body,
                status_code=status.HTTP_200_OK,
                media_type="application/json",
            )
            replay.headers["Idempotency-Replayed"] = "true"
            return replay

        response = await call_next(request)
        body = await _read_body(response)
        rebuilt = _rebuild_response(response, body)
        await _store_cached_response(redis_key, rebuilt.headers.items(), body)
        return rebuilt


async def _store_cached_response(redis_key: str, headers: Iterable[tuple[str, str]], body: bytes) -> None:
    if api_deps._redis_pool is None:
        return
    _ = headers
    if not body:
        return
    try:
        json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return
    await api_deps._redis_pool.setex(redis_key, IDEMPOTENCY_TTL_SECONDS, body.decode("utf-8"))


async def _read_body(response: Response) -> bytes:
    body = b""
    async for chunk in response.body_iterator:
        body += chunk
    return body


def _rebuild_response(response: Response, body: bytes) -> Response:
    rebuilt = Response(
        content=body,
        status_code=response.status_code,
        media_type=response.media_type,
        background=response.background,
    )
    for key, value in response.raw_headers:
        key_name = key.decode("latin-1").lower()
        if key_name == "content-length":
            continue
        rebuilt.raw_headers.append((key, value))
    return rebuilt
