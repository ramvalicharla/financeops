from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from financeops.api.v1.router import router as v1_router
from financeops.config import settings
from financeops.core.exceptions import FinanceOpsError, register_exception_handlers
from financeops.core.middleware import (
    CorrelationIdMiddleware,
    RequestLoggingMiddleware,
    RLSMiddleware,
)
from financeops.db.session import engine

log = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application startup and shutdown lifecycle."""
    log.info("FinanceOps starting up (env=%s)", settings.APP_ENV)

    # Run Alembic migrations on startup via subprocess (avoids asyncio/greenlet issues)
    try:
        import asyncio
        proc = await asyncio.create_subprocess_exec(
            "alembic", "upgrade", "head",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout, _ = await proc.communicate()
        if proc.returncode != 0:
            log.error("Alembic migration failed (rc=%d): %s", proc.returncode, stdout.decode())
        else:
            log.info("Alembic migrations applied: %s", stdout.decode().strip())
    except Exception as exc:
        log.error("Alembic migration error: %s", exc)

    # Initialize Redis pool
    try:
        import redis.asyncio as aioredis
        from financeops.api.deps import _redis_pool
        redis_client = aioredis.from_url(
            str(settings.REDIS_URL), encoding="utf-8", decode_responses=True
        )
        await redis_client.ping()
        log.info("Redis connection established")
    except Exception as exc:
        log.warning("Redis connection failed: %s", exc)

    yield

    # Shutdown
    log.info("FinanceOps shutting down")
    await engine.dispose()
    log.info("Database pool closed")


def create_app() -> FastAPI:
    """Application factory."""
    # Sentry initialization
    if settings.SENTRY_DSN:
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.APP_ENV,
            traces_sample_rate=0.1 if settings.APP_ENV == "production" else 1.0,
        )
        log.info("Sentry initialized")

    app = FastAPI(
        title=settings.APP_NAME,
        version="0.1.0",
        description="FinanceOps — Production-grade multi-tenant financial SaaS",
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
        lifespan=lifespan,
    )

    # Rate limiting
    limiter = Limiter(key_func=get_remote_address)
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
