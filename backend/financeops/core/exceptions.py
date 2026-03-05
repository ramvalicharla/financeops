from __future__ import annotations

import logging
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

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


def _error_response(
    request: Request,
    status_code: int,
    error_code: str,
    message: str,
) -> JSONResponse:
    correlation_id = getattr(request.state, "correlation_id", "unknown")
    return JSONResponse(
        status_code=status_code,
        content={
            "error": error_code,
            "message": message,
            "correlation_id": correlation_id,
        },
    )


async def financeops_error_handler(request: Request, exc: FinanceOpsError) -> JSONResponse:
    log.error(
        "FinanceOpsError: %s %s — %s",
        exc.error_code,
        exc.status_code,
        exc.message,
    )
    return _error_response(request, exc.status_code, exc.error_code, exc.message)


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    log.exception("Unhandled exception: %s", exc)
    return _error_response(
        request,
        500,
        "internal_error",
        "An unexpected error occurred. Please contact support.",
    )


def register_exception_handlers(app: Any) -> None:
    """Register all exception handlers on the FastAPI app."""
    app.add_exception_handler(FinanceOpsError, financeops_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)
