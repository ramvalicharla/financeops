from __future__ import annotations

import logging
from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from financeops.observability.business_metrics import (
    auth_failure_counter,
    upload_validation_failure_counter,
)
from financeops.shared_kernel.response import err

log = logging.getLogger(__name__)


class FinanceOpsError(Exception):
    """Base exception for all FinanceOps errors."""

    status_code: int = 500
    error_code: str = "internal_error"

    def __init__(self, message: str = "An internal error occurred") -> None:
        self.message = message
        super().__init__(message)


class AuthenticationError(FinanceOpsError):
    status_code = 401
    error_code = "authentication_error"

    def __init__(self, message: str = "Authentication required") -> None:
        super().__init__(message)


class AuthorizationError(FinanceOpsError):
    status_code = 403
    error_code = "authorization_error"

    def __init__(self, message: str = "Insufficient permissions") -> None:
        super().__init__(message)


class NotFoundError(FinanceOpsError):
    status_code = 404
    error_code = "not_found"

    def __init__(self, message: str = "Resource not found") -> None:
        super().__init__(message)


class ValidationError(FinanceOpsError):
    status_code = 422
    error_code = "validation_error"

    def __init__(self, message: str = "Validation failed") -> None:
        super().__init__(message)


class InsufficientCreditsError(FinanceOpsError):
    status_code = 402
    error_code = "insufficient_credits"

    def __init__(self, message: str = "Insufficient credits for this operation") -> None:
        super().__init__(message)


class StorageLimitExceededError(FinanceOpsError):
    status_code = 402
    error_code = "storage_limit_exceeded"

    def __init__(self, message: str = "Storage limit exceeded") -> None:
        super().__init__(message)


class ChainIntegrityError(FinanceOpsError):
    status_code = 500
    error_code = "chain_integrity_error"

    def __init__(self, message: str = "Audit chain integrity violation detected") -> None:
        super().__init__(message)


class TenantContextError(FinanceOpsError):
    status_code = 500
    error_code = "tenant_context_error"

    def __init__(self, message: str = "Tenant context not established") -> None:
        super().__init__(message)


class AllModelsFailedError(FinanceOpsError):
    status_code = 503
    error_code = "all_models_failed"

    def __init__(self, message: str = "All AI models in the fallback chain have failed") -> None:
        super().__init__(message)


class RateLimitError(FinanceOpsError):
    status_code = 429
    error_code = "rate_limit_exceeded"

    def __init__(self, message: str = "Rate limit exceeded") -> None:
        super().__init__(message)


class FeatureNotImplementedError(FinanceOpsError):
    """Feature exists in registry but is not yet implemented."""

    status_code = 501
    error_code = "feature_not_implemented"

    def __init__(self, feature: str, message: str = "") -> None:
        self.feature = feature
        super().__init__(message or f"Feature '{feature}' is not yet available.")


class PromptInjectionError(FinanceOpsError):
    status_code = 400
    error_code = "prompt_injection_detected"

    def __init__(self, message: str = "Request contains unsafe content and cannot be processed.") -> None:
        super().__init__(message)


def _error_response(
    request: Request,
    status_code: int,
    error_code: str,
    message: str,
    field: str | None = None,
    details: Any = None,
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    return JSONResponse(
        status_code=status_code,
        content=err(
            code=error_code,
            message=message,
            field=field,
            details=details,
            request_id=request_id,
        ).model_dump(mode="json"),
    )


async def financeops_error_handler(request: Request, exc: FinanceOpsError) -> JSONResponse:
    if exc.status_code in {401, 403}:
        auth_failure_counter.labels(failure_type=exc.error_code).inc()
    if "file_validation_failed" in str(exc.message):
        upload_validation_failure_counter.labels(module="api").inc()
    log.error(
        "financeops_error",
        extra={
            "event": "financeops_error",
            "error_code": exc.error_code,
            "status_code": exc.status_code,
            "error_message": exc.message,
            "path": request.url.path,
        },
    )
    return _error_response(request, exc.status_code, exc.error_code, exc.message)


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    log.exception(
        "unhandled_exception",
        extra={
            "event": "unhandled_exception",
            "error_type": exc.__class__.__name__,
            "path": request.url.path,
        },
    )
    return _error_response(
        request,
        500,
        "internal_error",
        "An unexpected error occurred. Please contact support.",
    )


async def feature_not_implemented_handler(
    request: Request,
    exc: FeatureNotImplementedError,
) -> JSONResponse:
    _ = request
    return JSONResponse(
        status_code=501,
        content={"error": "feature_not_implemented", "feature": exc.feature},
    )


async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    detail = exc.detail
    field: str | None = None
    details: Any = None
    error_code = f"http_{exc.status_code}"
    message: str

    if isinstance(detail, list):
        message = "Validation failed"
        if detail and isinstance(detail[0], dict):
            loc = detail[0].get("loc")
            if isinstance(loc, list) and loc:
                field = ".".join(str(item) for item in loc if item != "body")
    elif isinstance(detail, dict):
        message = str(detail.get("message", "Request failed"))
        if isinstance(detail.get("code"), str):
            error_code = detail["code"]
        if isinstance(detail.get("field"), str):
            field = detail["field"]
        details = {
            key: value
            for key, value in detail.items()
            if key not in {"code", "message", "field"}
        } or None
    else:
        message = str(detail)

    if exc.status_code in {401, 403}:
        auth_failure_counter.labels(failure_type=f"http_{exc.status_code}").inc()
    if isinstance(detail, str) and "file_validation_failed" in detail:
        upload_validation_failure_counter.labels(module="api").inc()

    return _error_response(
        request,
        exc.status_code,
        error_code,
        message,
        field=field,
        details=details,
    )


async def request_validation_error_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    field: str | None = None
    errors = exc.errors()
    if errors and isinstance(errors[0], dict):
        loc = errors[0].get("loc")
        if isinstance(loc, list) and loc:
            field = ".".join(str(item) for item in loc if item != "body")
    return _error_response(
        request,
        422,
        "validation_error",
        "Validation failed",
        field=field,
    )


def register_exception_handlers(app: Any) -> None:
    """Register all exception handlers on the FastAPI app."""
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, request_validation_error_handler)
    app.add_exception_handler(FeatureNotImplementedError, feature_not_implemented_handler)
    app.add_exception_handler(FinanceOpsError, financeops_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)
