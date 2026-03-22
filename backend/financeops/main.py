from __future__ import annotations

import os
import re
import logging
import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator

import filelock
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette_csrf import CSRFMiddleware
from alembic import command
from alembic.config import Config

from financeops.api.v1.router import router as v1_router
from financeops.config import limiter, settings
from financeops.core.exceptions import FinanceOpsError, register_exception_handlers
from financeops.modules.anomaly_pattern_engine.api.anomaly_ui_routes import (
    router as anomaly_ui_router,
)
from financeops.modules.auto_trigger.api.routes import router as auto_trigger_router
from financeops.modules.board_pack_generator.api.routes import router as board_pack_router
from financeops.modules.custom_report_builder.api.routes import router as report_router
from financeops.modules.scheduled_delivery.api.routes import router as scheduled_delivery_router
from financeops.modules.secret_rotation.api.routes import router as secret_rotation_router
from financeops.modules.template_onboarding.api.routes import router as onboarding_router
from financeops.modules.compliance.api.routes import router as compliance_router
from financeops.core.middleware import (
    CorrelationIdMiddleware,
    RequestLoggingMiddleware,
    RLSMiddleware,
)
from financeops.observability.logging import configure_logging
from financeops.observability.middleware import LoggingMiddleware
from financeops.observability.sentry import configure_sentry
from financeops.observability import business_metrics as _business_metrics  # noqa: F401
from financeops.shared_kernel.response import (
    ApiResponseEnvelopeMiddleware,
    RequestIDMiddleware,
)
from financeops.shared_kernel.idempotency import IdempotencyMiddleware
from financeops.db.session import engine

log = logging.getLogger(__name__)
configure_logging(log_level=settings.LOG_LEVEL)

def run_migrations_with_lock() -> None:
    """
    Run Alembic migrations at startup with an exclusive file lock.
    Only one worker executes migrations while others wait.
    """
    lock_path = os.environ.get("MIGRATION_LOCK_PATH", "/tmp/financeops_migration.lock")
    alembic_cfg = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    try:
        with filelock.FileLock(lock_path, timeout=60):
            command.upgrade(alembic_cfg, "head")
    except filelock.Timeout as exc:
        raise RuntimeError(
            "Migration lock timeout after 60 seconds. "
            "Check for a stuck migration process or a failed migration."
        ) from exc


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application startup and shutdown lifecycle."""
    log.info("FinanceOps starting up (env=%s)", settings.APP_ENV)
    configure_sentry(
        dsn=settings.SENTRY_DSN,
        environment=settings.APP_ENVIRONMENT,
        release=settings.APP_RELEASE,
    )

    log.info("Running database migrations...")
    run_migrations_with_lock()
    log.info("Database migrations complete.")

    # Initialize Redis pool
    try:
        import redis.asyncio as aioredis
        from financeops.api import deps as api_deps
        redis_client = aioredis.from_url(
            str(settings.REDIS_URL), encoding="utf-8", decode_responses=True
        )
        await redis_client.ping()
        api_deps._redis_pool = redis_client
        log.info("Redis connection established")
    except Exception as exc:
        log.warning("Redis connection failed: %s", exc)

    temporal_worker_task: asyncio.Task | None = None
    if settings.TEMPORAL_WORKER_IN_PROCESS:
        try:
            from financeops.workers.temporal_worker import run_worker

            temporal_worker_task = asyncio.create_task(run_worker())
            log.info("Temporal worker task started in-process")
        except Exception as exc:
            log.warning("Temporal worker start failed: %s", exc)

    yield

    # Shutdown
    log.info("FinanceOps shutting down")
    if temporal_worker_task is not None:
        temporal_worker_task.cancel()
        try:
            await temporal_worker_task
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            log.warning("Temporal worker task shutdown failed: %s", exc)
    try:
        from financeops.api import deps as api_deps
        redis_pool = api_deps._redis_pool
        if redis_pool is not None:
            await redis_pool.aclose()
            api_deps._redis_pool = None
            log.info("Redis pool closed")
    except Exception as exc:
        log.warning("Redis pool close failed: %s", exc)
    await engine.dispose()
    log.info("Database pool closed")


def create_app() -> FastAPI:
    """Application factory."""
    app = FastAPI(
        title=settings.APP_NAME,
        version="0.1.0",
        description="FinanceOps — Production-grade multi-tenant financial SaaS",
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
        lifespan=lifespan,
    )

    environment = str(getattr(settings, "ENVIRONMENT", settings.APP_ENV)).lower()
    app.add_middleware(
        CSRFMiddleware,
        secret=settings.SECRET_KEY,
        exempt_urls=[
            re.compile(r"^/api/v1/auth(?:/.*)?$"),
            re.compile(r"^/health(?:/.*)?$"),
            re.compile(r"^/metrics(?:/.*)?$"),
            re.compile(r"^/.*webhooks?(?:/.*)?$"),
            re.compile(r"^/api/v1/.*webhooks?(?:/.*)?$"),
        ],
        cookie_secure=environment == "production",
        cookie_samesite="strict",
    )

    # Rate limiting
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # CORS
    allowed_origins = (
        ["*"] if settings.APP_ENV == "development"
        else [f"https://{settings.APP_NAME.lower()}.com"]
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Custom middlewares (order matters: last added = outermost)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(RLSMiddleware)
    app.add_middleware(CorrelationIdMiddleware)
    app.add_middleware(IdempotencyMiddleware)
    app.add_middleware(ApiResponseEnvelopeMiddleware)
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(LoggingMiddleware)

    # Exception handlers
    register_exception_handlers(app)

    # Prometheus metrics
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)

    # Health endpoint (no prefix — accessible at root)
    from financeops.api.v1.health import router as health_router
    app.include_router(health_router, prefix="/health", tags=["Health"])

    # API v1
    app.include_router(v1_router, prefix="/api/v1")
    app.include_router(board_pack_router, prefix="/api/v1")
    app.include_router(report_router, prefix="/api/v1")
    app.include_router(scheduled_delivery_router, prefix="/api/v1")
    app.include_router(anomaly_ui_router, prefix="/api/v1")
    app.include_router(auto_trigger_router, prefix="/api/v1")
    app.include_router(onboarding_router, prefix="/api/v1")
    app.include_router(secret_rotation_router, prefix="/api/v1")
    app.include_router(compliance_router, prefix="/api/v1")

    # OpenTelemetry instrumentation
    if settings.OTEL_EXPORTER_OTLP_ENDPOINT:
        try:
            from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
            FastAPIInstrumentor.instrument_app(app)
            log.info("OpenTelemetry FastAPI instrumentation enabled")
        except Exception as exc:
            log.warning("OTel FastAPI instrumentation failed: %s", exc)

    log.info("FastAPI application created with %d routes", len(app.routes))
    return app


app = create_app()
