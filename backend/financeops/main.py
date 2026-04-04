from __future__ import annotations

import re
import os
import logging
import asyncio
import sys
from importlib.metadata import PackageNotFoundError, version as package_version
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from prometheus_client import make_asgi_app
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from sqlalchemy.engine import make_url

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

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
from financeops.modules.closing_checklist.api.routes import router as closing_checklist_router
from financeops.modules.working_capital.api.routes import router as working_capital_router
from financeops.modules.expense_management.api.routes import router as expense_router
from financeops.modules.budgeting.api.routes import router as budgeting_router
from financeops.modules.forecasting.api.routes import router as forecasting_router
from financeops.modules.scenario_modelling.api.routes import router as scenario_router
from financeops.modules.backup.api.routes import router as backup_router
from financeops.api.v1.platform_users import router as platform_users_router
from financeops.modules.fdd.api.routes import router as fdd_router
from financeops.modules.ppa.api.routes import router as ppa_router
from financeops.modules.ma_workspace.api.routes import router as ma_router
from financeops.modules.service_registry.api.routes import router as service_registry_router
from financeops.modules.marketplace.api.routes import router as marketplace_router
from financeops.modules.white_label.api.routes import router as white_label_router
from financeops.modules.partner.api.routes import router as partner_router
from financeops.modules.notifications.api.routes import router as notifications_router
from financeops.modules.learning_engine.api.routes import router as learning_router
from financeops.modules.search.api.routes import router as search_router
from financeops.modules.cash_flow_forecast.api.routes import router as treasury_router
from financeops.modules.tax_provision.api.routes import router as tax_router
from financeops.modules.debt_covenants.api.routes import router as covenants_router
from financeops.modules.transfer_pricing.api.routes import router as tp_router
from financeops.modules.digital_signoff.api.routes import router as signoff_router
from financeops.modules.statutory.api.routes import router as statutory_router
from financeops.modules.multi_gaap.api.routes import router as gaap_router
from financeops.modules.auditor_portal.api.routes import router as audit_router
from financeops.modules.coa.api.routes import router as coa_router
from financeops.modules.org_setup.api.routes import router as org_setup_router
from financeops.modules.fixed_assets.api.routes import router as fa_router
from financeops.modules.prepaid_expenses.api.routes import router as prepaid_router
from financeops.modules.invoice_classifier.api.routes import router as classifier_router
from financeops.modules.locations.api.routes import router as locations_router
from financeops.api.v1.ai_stream import router as ai_stream_router
from financeops.api.v1.admin_ai_providers import router as admin_ai_providers_router
from financeops.api.v1.debug_network import router as debug_network_router
from financeops.api.deps import require_org_setup
from financeops.core.middleware import (
    CorrelationIdMiddleware,
    FinanceOpsCSRFMiddleware,
    RequestSizeLimitMiddleware,
    RequestLoggingMiddleware,
    RLSMiddleware,
)
from financeops.observability.logging import configure_logging
from financeops.observability.middleware import LoggingMiddleware
from financeops.observability.sentry import configure_sentry
from financeops.observability.tracing import configure_telemetry
from financeops.observability import business_metrics as _business_metrics  # noqa: F401
from financeops.shared_kernel.response import (
    ApiResponseEnvelopeMiddleware,
    RequestIDMiddleware,
)
from financeops.shared_kernel.idempotency import IdempotencyMiddleware
from financeops.core.migration_checker import enforce_migration_state
from financeops.db.session import engine
from financeops.migrations.run import run_migrations_to_head
from financeops.seed.coa import seed_coa_industry_templates

log = logging.getLogger(__name__)
configure_logging(log_level=settings.LOG_LEVEL)

try:
    APP_VERSION = package_version("financeops-backend")
except PackageNotFoundError:
    APP_VERSION = settings.APP_RELEASE

DB_CONNECTIVITY_HINT = (
    "Database connection failed.\n"
    "Check:\n"
    "- DATABASE_URL correctness\n"
    "- host reachability\n"
    "- network/firewall\n"
    "- docker vs local mismatch"
)


def _masked_database_url(raw_url: str) -> str:
    """Render DATABASE_URL with password masked for safe logging."""
    try:
        return make_url(raw_url).render_as_string(hide_password=True)
    except Exception:
        return "<invalid DATABASE_URL>"


def _exception_text(exc: Exception) -> str:
    """Return a stable, non-empty exception text for logs."""
    text_value = str(exc).strip()
    return text_value or exc.__class__.__name__


def _resolve_cors_origins() -> list[str]:
    """
    Resolve CORS origins from env.

    Priority:
      1) CORS_ORIGINS (comma-separated)
      2) CORS_ALLOWED_ORIGINS (legacy compatibility)
      3) localhost fallback
    """
    raw_cors_origins = os.getenv("CORS_ORIGINS", "").strip()
    if raw_cors_origins:
        parsed = [origin.strip() for origin in raw_cors_origins.split(",") if origin.strip()]
        if parsed:
            return parsed

    raw_legacy_origins = os.getenv("CORS_ALLOWED_ORIGINS", "").strip()
    if raw_legacy_origins:
        parsed = [origin.strip() for origin in raw_legacy_origins.split(",") if origin.strip()]
        if parsed:
            return parsed

    return ["http://localhost:3000"]


async def _check_database_connectivity() -> None:
    """Verify database connectivity during application startup."""
    async def _ping_database() -> None:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

    try:
        await asyncio.wait_for(_ping_database(), timeout=5.0)
    except Exception as exc:
        detail = _exception_text(exc)
        log.error("%s Detail: %s", DB_CONNECTIVITY_HINT, detail)
        raise RuntimeError(f"{DB_CONNECTIVITY_HINT}\nDetail: {detail}") from exc


async def _initialize_redis_pool() -> None:
    """Initialize the shared Redis connection pool during startup."""
    try:
        import redis.asyncio as aioredis
        from financeops.api import deps as api_deps

        redis_client = aioredis.from_url(
            str(settings.REDIS_URL), encoding="utf-8", decode_responses=True
        )
        await asyncio.wait_for(redis_client.ping(), timeout=2.0)
        api_deps._redis_pool = redis_client
        log.info("Redis connection established")
    except Exception as exc:
        log.warning("Redis connection failed: %s", _exception_text(exc))


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application startup and shutdown lifecycle."""
    log.info("FinanceOps starting up (env=%s)", settings.APP_ENV)
    log.info("DATABASE_URL in use: %s", _masked_database_url(str(settings.DATABASE_URL)))
    startup_errors: list[str] = []
    app.state.startup_errors = startup_errors
    app.state.migration_state = {
        "status": "unknown",
        "current_revision": None,
        "head_revision": None,
        "detail": "startup check pending",
    }
    configure_sentry(
        dsn=settings.SENTRY_DSN,
        environment=settings.APP_ENVIRONMENT,
        release=settings.APP_RELEASE,
    )
    is_production = settings.APP_ENV.lower() == "production"
    migration_fail_fast = settings.MIGRATION_FAIL_FAST or is_production

    db_check_task = asyncio.create_task(_check_database_connectivity())
    redis_init_task = asyncio.create_task(_initialize_redis_pool())

    try:
        await db_check_task
    except Exception as exc:
        error_text = _exception_text(exc)
        message = (
            "Database connectivity check failed during startup: "
            f"{error_text}"
        )
        startup_errors.append(message)
        log.error(message)
        raise RuntimeError(message) from exc
    else:
        log.info("Database connectivity check passed.")
        if settings.AUTO_MIGRATE:
            if is_production:
                log.warning("AUTO_MIGRATE=true ignored because APP_ENV=production")
            else:
                try:
                    await asyncio.to_thread(run_migrations_to_head)
                    log.info("AUTO_MIGRATE=true: alembic upgrade head completed")
                except Exception as exc:
                    message = (
                        "Automatic migration failed during startup: "
                        f"{_exception_text(exc)}"
                    )
                    startup_errors.append(message)
                    log.critical(message)
                    if migration_fail_fast:
                        raise RuntimeError(message)

        try:
            migration_result = await enforce_migration_state(fail_fast=migration_fail_fast)
            app.state.migration_state = migration_result.to_dict()
            if migration_result.current_revision != migration_result.head_revision:
                mismatch_message = (
                    f"Migration mismatch: current={migration_result.current_revision}, "
                    f"head={migration_result.head_revision}. "
                    "Run migrations before starting the app."
                )
                app.state.migration_state = {
                    "status": "out_of_sync",
                    "current_revision": migration_result.current_revision,
                    "head_revision": migration_result.head_revision,
                    "detail": mismatch_message,
                }
                startup_errors.append(mismatch_message)
                log.error("Migration mismatch detected - startup aborted")
                raise RuntimeError(mismatch_message)

            if migration_result.status != "ok":
                status_message = migration_result.detail or "Migration state unknown."
                app.state.migration_state = {
                    "status": migration_result.status,
                    "current_revision": migration_result.current_revision,
                    "head_revision": migration_result.head_revision,
                    "detail": status_message,
                }
                startup_errors.append(status_message)
                log.error("Migration mismatch detected - startup aborted")
                raise RuntimeError(status_message)

            log.info(
                "Migrations verified: current == head (%s)",
                migration_result.head_revision,
            )
        except Exception as exc:
            if str(exc).startswith("Migration mismatch:"):
                message = str(exc)
            else:
                message = f"DB schema out of sync with code: {_exception_text(exc)}"
                app.state.migration_state = {
                    "status": "out_of_sync",
                    "current_revision": None,
                    "head_revision": None,
                    "detail": message,
                }
                startup_errors.append(message)
            log.error("Migration mismatch detected - startup aborted")
            log.critical(message)
            if message.startswith("Migration mismatch:"):
                raise RuntimeError(message)
            if migration_fail_fast:
                raise RuntimeError(message)

        if app.state.migration_state.get("status") == "ok":
            try:
                await seed_coa_industry_templates()
                log.info("CoA seed completed (startup)")
            except Exception as exc:
                log.error("CoA seed failed: %s", exc)
        else:
            log.warning("Skipping CoA seed because migration state is not OK")

    await redis_init_task

    yield

    # Shutdown
    log.info("FinanceOps shutting down")
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
        version=APP_VERSION,
        description="FinanceOps — Production-grade multi-tenant financial SaaS",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    environment = str(getattr(settings, "ENVIRONMENT", settings.APP_ENV)).lower()
    app.add_middleware(
        FinanceOpsCSRFMiddleware,
        secret=settings.SECRET_KEY,
        exempt_urls=[
            re.compile(r"^/api(?:/.*)?$"),
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

    # Custom middlewares (order matters: last added = outermost)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(RLSMiddleware)
    app.add_middleware(CorrelationIdMiddleware)
    app.add_middleware(RequestSizeLimitMiddleware)
    app.add_middleware(IdempotencyMiddleware)
    app.add_middleware(ApiResponseEnvelopeMiddleware)
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(GZipMiddleware, minimum_size=1024)

    # CORS (registered last so it executes before custom middleware in Starlette)
    resolved_origins = _resolve_cors_origins()
    log.info("CORS middleware applied with origins: %s", resolved_origins)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Exception handlers
    register_exception_handlers(app)

    # Prometheus metrics
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)

    # Health endpoint (no prefix — accessible at root)
    from financeops.api.v1.health import (
        build_health_summary_payload,
        build_liveness_payload,
        build_readiness_payload,
        router as health_router,
    )
    app.include_router(health_router, prefix="/health", tags=["Health"])
    app.include_router(debug_network_router)

    @app.get("/live", tags=["Health"])
    async def live_root() -> dict[str, object]:
        return build_liveness_payload()

    @app.get("/ready", tags=["Health"])
    async def ready_root() -> JSONResponse:
        startup_errors = getattr(app.state, "startup_errors", [])
        migration_state = getattr(app.state, "migration_state", None)
        payload, code = await build_readiness_payload(
            startup_errors=startup_errors,
            migration_state=migration_state,
        )
        return JSONResponse(content=payload, status_code=code)

    @app.get("/healthz", tags=["Health"])
    async def healthz_alias(request: Request) -> JSONResponse:
        startup_errors = getattr(request.app.state, "startup_errors", [])
        payload = await build_health_summary_payload(startup_errors=startup_errors)
        return JSONResponse(content=payload, status_code=200)

    @app.get("/readyz", tags=["Health"])
    async def readyz_alias(request: Request) -> JSONResponse:
        startup_errors = getattr(request.app.state, "startup_errors", [])
        migration_state = getattr(request.app.state, "migration_state", None)
        payload, code = await build_readiness_payload(
            startup_errors=startup_errors,
            migration_state=migration_state,
        )
        return JSONResponse(content=payload, status_code=code)

    # API v1
    org_setup_dependency = [Depends(require_org_setup)]
    app.include_router(v1_router, prefix="/api/v1")
    app.include_router(board_pack_router, prefix="/api/v1", dependencies=org_setup_dependency)
    app.include_router(report_router, prefix="/api/v1", dependencies=org_setup_dependency)
    app.include_router(scheduled_delivery_router, prefix="/api/v1", dependencies=org_setup_dependency)
    app.include_router(anomaly_ui_router, prefix="/api/v1", dependencies=org_setup_dependency)
    app.include_router(auto_trigger_router, prefix="/api/v1", dependencies=org_setup_dependency)
    app.include_router(onboarding_router, prefix="/api/v1")
    app.include_router(secret_rotation_router, prefix="/api/v1", dependencies=org_setup_dependency)
    app.include_router(compliance_router, prefix="/api/v1", dependencies=org_setup_dependency)
    app.include_router(closing_checklist_router, prefix="/api/v1", dependencies=org_setup_dependency)
    app.include_router(working_capital_router, prefix="/api/v1", dependencies=org_setup_dependency)
    app.include_router(expense_router, prefix="/api/v1", dependencies=org_setup_dependency)
    app.include_router(budgeting_router, prefix="/api/v1", dependencies=org_setup_dependency)
    app.include_router(forecasting_router, prefix="/api/v1", dependencies=org_setup_dependency)
    app.include_router(scenario_router, prefix="/api/v1", dependencies=org_setup_dependency)
    app.include_router(backup_router, prefix="/api/v1", dependencies=org_setup_dependency)
    app.include_router(platform_users_router, prefix="/api/v1", dependencies=org_setup_dependency)
    app.include_router(fdd_router, prefix="/api/v1", dependencies=org_setup_dependency)
    app.include_router(ppa_router, prefix="/api/v1", dependencies=org_setup_dependency)
    app.include_router(ma_router, prefix="/api/v1", dependencies=org_setup_dependency)
    app.include_router(service_registry_router, prefix="/api/v1", dependencies=org_setup_dependency)
    app.include_router(marketplace_router, prefix="/api/v1", dependencies=org_setup_dependency)
    app.include_router(white_label_router, prefix="/api/v1")
    app.include_router(partner_router, prefix="/api/v1")
    app.include_router(notifications_router, prefix="/api/v1", dependencies=org_setup_dependency)
    app.include_router(learning_router, prefix="/api/v1", dependencies=org_setup_dependency)
    app.include_router(search_router, prefix="/api/v1", dependencies=org_setup_dependency)
    app.include_router(treasury_router, prefix="/api/v1", dependencies=org_setup_dependency)
    app.include_router(tax_router, prefix="/api/v1", dependencies=org_setup_dependency)
    app.include_router(covenants_router, prefix="/api/v1", dependencies=org_setup_dependency)
    app.include_router(tp_router, prefix="/api/v1", dependencies=org_setup_dependency)
    app.include_router(signoff_router, prefix="/api/v1", dependencies=org_setup_dependency)
    app.include_router(statutory_router, prefix="/api/v1", dependencies=org_setup_dependency)
    app.include_router(gaap_router, prefix="/api/v1", dependencies=org_setup_dependency)
    app.include_router(audit_router, prefix="/api/v1")
    app.include_router(coa_router, prefix="/api/v1", tags=["chart-of-accounts"])
    app.include_router(org_setup_router, prefix="/api/v1", tags=["org-setup"])
    app.include_router(fa_router, prefix="/api/v1", tags=["fixed-assets"], dependencies=org_setup_dependency)
    app.include_router(prepaid_router, prefix="/api/v1", tags=["prepaid"], dependencies=org_setup_dependency)
    app.include_router(classifier_router, prefix="/api/v1", tags=["invoice-classifier"], dependencies=org_setup_dependency)
    app.include_router(locations_router, prefix="/api/v1", tags=["locations"], dependencies=org_setup_dependency)
    app.include_router(ai_stream_router, prefix="/api/v1", dependencies=org_setup_dependency)
    app.include_router(admin_ai_providers_router, prefix="/api/v1", dependencies=org_setup_dependency)

    # OpenTelemetry instrumentation
    configure_telemetry(app=app, engine=engine, settings=settings)

    log.info("FastAPI application created with %d routes", len(app.routes))
    return app


app = create_app()
