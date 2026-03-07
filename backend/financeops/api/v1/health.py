from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user
from financeops.db.models.users import IamUser
from financeops.db.session import check_db_health
from financeops.utils.formatting import utc_now_iso

log = logging.getLogger(__name__)
router = APIRouter()


@router.get("")
async def health_check() -> dict:
    """
    GET /health
    No auth required. Used by Railway health check.
    """
    return {
        "status": "ok",
        "timestamp": utc_now_iso(),
        "version": "0.1.0",
    }


@router.get("/deep")
async def deep_health_check(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    """
    GET /api/v1/health/deep
    Auth required. Checks DB, Redis, and storage connections.
    Used by Cloudflare health check for failover.
    """
    db_status = await check_db_health()

    redis_status = {"status": "ok"}
    try:
        from financeops.api.deps import _redis_pool
        if _redis_pool is not None:
            await _redis_pool.ping()
        else:
            redis_status = {"status": "not_initialized"}
    except Exception as exc:
        redis_status = {"status": "error", "detail": str(exc)}

    storage_status = {"status": "ok"}
    try:
        from financeops.config import settings
        if not settings.R2_ENDPOINT_URL:
            storage_status = {"status": "not_configured"}
    except Exception as exc:
        storage_status = {"status": "error", "detail": str(exc)}

    temporal_status = {"status": "not_initialized"}
    try:
        from financeops.temporal.client import check_temporal_health

        temporal_status = await check_temporal_health()
    except Exception as exc:
        temporal_status = {"status": "error", "detail": str(exc)}

    checks = {
        "db": db_status,
        "redis": redis_status,
        "storage": storage_status,
        "temporal": temporal_status,
    }
    overall = (
        "ok"
        if all(
            v["status"] in ("ok", "not_configured", "not_initialized")
            for v in checks.values()
        )
        else "degraded"
    )

    return {
        "status": overall,
        "timestamp": utc_now_iso(),
        "version": "0.1.0",
        "checks": checks,
    }
