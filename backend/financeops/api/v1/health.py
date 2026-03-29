from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any

import httpx
import redis.asyncio as aioredis
from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user
from financeops.config import settings
from financeops.db.models.users import IamUser
from financeops.db.session import AsyncSessionLocal, engine
from financeops.observability.celery_monitor import get_celery_monitor
from financeops.tasks.celery_app import celery_app
from financeops.temporal.client import check_temporal_health
from financeops.utils.formatting import utc_now_iso

log = logging.getLogger(__name__)
router = APIRouter()


def _latency_ms(started_at: float) -> float:
    return round((time.perf_counter() - started_at) * 1000, 2)


async def _check_database() -> dict[str, Any]:
    started_at = time.perf_counter()
    try:
        async with AsyncSessionLocal() as session:
            await asyncio.wait_for(session.execute(text("SELECT 1")), timeout=2.0)
        return {"status": "healthy", "latency_ms": _latency_ms(started_at)}
    except Exception:
        return {"status": "unhealthy", "latency_ms": _latency_ms(started_at)}


async def _check_redis() -> dict[str, Any]:
    started_at = time.perf_counter()
    client: aioredis.Redis | None = None
    try:
        client = aioredis.from_url(
            str(settings.REDIS_URL),
            encoding="utf-8",
            decode_responses=True,
        )
        await asyncio.wait_for(client.ping(), timeout=1.0)
        return {"status": "healthy", "latency_ms": _latency_ms(started_at)}
    except Exception:
        return {"status": "unhealthy", "latency_ms": _latency_ms(started_at)}
    finally:
        if client is not None:
            await client.aclose()


def _inspect_active_workers() -> int:
    inspector = celery_app.control.inspect(timeout=1.0)
    ping = inspector.ping() if inspector is not None else None
    if not ping:
        return 0
    return len(ping)


async def _check_workers() -> dict[str, Any]:
    started_at = time.perf_counter()
    try:
        workers = await asyncio.wait_for(
            asyncio.to_thread(_inspect_active_workers),
            timeout=1.5,
        )
        return {
            "status": "healthy" if workers > 0 else "no_workers",
            "active_workers": workers,
            "latency_ms": _latency_ms(started_at),
        }
    except Exception:
        return {
            "status": "no_workers",
            "active_workers": 0,
            "latency_ms": _latency_ms(started_at),
        }


async def _check_migrations() -> dict[str, Any]:
    started_at = time.perf_counter()
    alembic_ini = os.path.join(os.path.dirname(__file__), "..", "..", "..", "alembic.ini")
    alembic_cfg = Config(os.path.abspath(alembic_ini))
    script_dir = ScriptDirectory.from_config(alembic_cfg)
    head = script_dir.get_current_head()

    current: str | None = None
    try:
        async with engine.connect() as conn:
            result = await asyncio.wait_for(
                conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1")),
                timeout=1.0,
            )
            current = result.scalar_one_or_none()
    except Exception:
        return {
            "status": "error",
            "latency_ms": _latency_ms(started_at),
            "current_head": head,
        }

    return {
        "status": "ok" if current == head else "error",
        "latency_ms": _latency_ms(started_at),
        "current_head": head,
    }


async def _check_ai() -> dict[str, Any]:
    ollama_status = "down"
    ollama_url = settings.OLLAMA_BASE_URL.rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(f"{ollama_url}/api/tags")
        if response.status_code == 200:
            ollama_status = "up"
    except Exception:
        ollama_status = "down"

    anthropic_configured = bool(settings.ANTHROPIC_API_KEY.strip())
    openai_configured = bool(settings.OPENAI_API_KEY.strip())
    fallback_available = (
        ollama_status == "up" or anthropic_configured or openai_configured
    )

    if not fallback_available:
        status_value = "unhealthy"
    elif ollama_status == "down":
        status_value = "degraded"
    else:
        status_value = "healthy"

    return {
        "status": status_value,
        "ollama": ollama_status if settings.OLLAMA_BASE_URL else "not_configured",
        "anthropic": "configured" if anthropic_configured else "not_configured",
        "openai": "configured" if openai_configured else "not_configured",
        "fallback_available": fallback_available,
    }


async def _check_queues() -> dict[str, Any]:
    monitor = get_celery_monitor()
    depths = await monitor.get_queue_depths()
    response: dict[str, dict[str, Any]] = {}
    any_backlog = False
    for queue_name in ("file_scan", "erp_sync", "report_gen", "ai_inference"):
        depth = int(depths.get(queue_name, 0))
        queue_status = "backlogged" if depth > 100 else "ok"
        if queue_status == "backlogged":
            any_backlog = True
        response[queue_name] = {"depth": depth, "status": queue_status}
    return {
        "status": "degraded" if any_backlog else "healthy",
        "queues": response,
    }


async def _check_temporal() -> dict[str, str]:
    health = await check_temporal_health()
    return {
        "status": "up" if health.get("status") == "ok" else "down",
        "address": settings.TEMPORAL_ADDRESS,
        "namespace": settings.TEMPORAL_NAMESPACE,
    }


async def _build_health_payload() -> dict[str, Any]:
    db_check, redis_check, ai_check, queue_check, temporal_check, workers_check, migration_check = await asyncio.gather(
        _check_database(),
        _check_redis(),
        _check_ai(),
        _check_queues(),
        _check_temporal(),
        _check_workers(),
        _check_migrations(),
    )

    checks = {
        "database": db_check["status"],
        "redis": redis_check["status"],
        "ai": ai_check["status"],
        "queues": queue_check["status"],
        "temporal": temporal_check["status"],
        "workers": workers_check["status"],
        # Backward-compatible aliases used by existing tests.
        "db": {"status": "ok" if db_check["status"] == "healthy" else "error"},
        "celery": {"status": "ok" if workers_check["status"] == "healthy" else "error"},
        "migrations": migration_check,
    }

    if settings.APP_ENVIRONMENT.lower() != "production":
        overall = "healthy" if checks["database"] == "healthy" and checks["redis"] == "healthy" else "degraded"
    else:
        if checks["database"] == "unhealthy" or checks["redis"] == "unhealthy" or checks["ai"] == "unhealthy":
            overall = "unhealthy"
        elif checks["ai"] == "degraded" or checks["queues"] == "degraded" or checks["workers"] == "no_workers":
            overall = "degraded"
        else:
            overall = "healthy"

    legacy_status = "ok" if overall == "healthy" else overall

    return {
        "status": legacy_status,
        "health_status": overall,
        "checks": checks,
        "ai": ai_check,
        "queues": queue_check["queues"],
        "temporal": temporal_check,
        "workers": {
            "status": workers_check["status"],
            "active_workers": workers_check["active_workers"],
        },
        "version": settings.APP_RELEASE,
        "environment": settings.APP_ENVIRONMENT,
        "timestamp": utc_now_iso(),
    }


@router.get("")
async def health_check(request: Request) -> JSONResponse:
    startup_errors = getattr(request.app.state, "startup_errors", [])
    payload = {
        "status": "ok",
        "health_status": "healthy" if not startup_errors else "degraded",
        "version": settings.APP_RELEASE,
        "environment": settings.APP_ENVIRONMENT,
        "timestamp": utc_now_iso(),
        "startup_errors": startup_errors,
    }
    return JSONResponse(content=payload, status_code=status.HTTP_200_OK)


@router.get("/deep")
async def deep_health_check(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> JSONResponse:
    del session, user
    payload = await asyncio.wait_for(_build_health_payload(), timeout=5.0)
    return JSONResponse(content=payload, status_code=status.HTTP_200_OK)


@router.get("/ai")
async def health_ai() -> JSONResponse:
    return JSONResponse(content=await _check_ai(), status_code=status.HTTP_200_OK)


@router.get("/queues")
async def health_queues() -> JSONResponse:
    return JSONResponse(content=await _check_queues(), status_code=status.HTTP_200_OK)


@router.get("/temporal")
async def health_temporal() -> JSONResponse:
    return JSONResponse(content=await _check_temporal(), status_code=status.HTTP_200_OK)


@router.get("/workers")
async def health_workers() -> JSONResponse:
    return JSONResponse(content=await _check_workers(), status_code=status.HTTP_200_OK)
