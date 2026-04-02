from __future__ import annotations

import hashlib
import json
import uuid
from datetime import date
from typing import Any

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user, get_redis
from financeops.core.exceptions import AuthorizationError
from financeops.db.models.users import IamUser, UserRole
from financeops.modules.analytics_layer.application.alert_service import (
    create_alert,
    evaluate_alerts,
    list_alerts,
)
from financeops.modules.analytics_layer.application.budget_service import get_budget_variance
from financeops.modules.analytics_layer.application.drilldown_service import get_metric_drilldown
from financeops.modules.analytics_layer.application.kpi_service import compute_kpis
from financeops.modules.analytics_layer.application.ratio_service import compute_ratios
from financeops.modules.analytics_layer.application.trend_service import compute_trends
from financeops.modules.analytics_layer.application.variance_service import compute_variance
from financeops.modules.analytics_layer.schemas import AlertCreateRequest
from financeops.shared_kernel.response import ok

router = APIRouter(prefix="/analytics", tags=["Analytics"])
_CACHE_TTL_SECONDS = 120
_CACHE_VERSION_KEY_PREFIX = "analytics:version"
_CACHE_KEY_PREFIX = "analytics:read"

_ALLOWED_ROLES = {
    UserRole.super_admin,
    UserRole.platform_owner,
    UserRole.platform_admin,
    UserRole.finance_leader,
    UserRole.finance_team,
    UserRole.auditor,
}


def _assert_analytics_access(user: IamUser) -> None:
    if user.role not in _ALLOWED_ROLES:
        raise AuthorizationError("Analytics access requires finance/admin role.")


def _query_signature(request: Request) -> str:
    pairs = sorted((str(key), str(value)) for key, value in request.query_params.multi_items())
    raw = "&".join(f"{key}={value}" for key, value in pairs)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def _analytics_cache_version(redis_client: aioredis.Redis | None, *, tenant_id: uuid.UUID) -> int:
    if redis_client is None:
        return 1
    try:
        value = await redis_client.get(f"{_CACHE_VERSION_KEY_PREFIX}:{tenant_id}")
        if value is None:
            await redis_client.setex(
                name=f"{_CACHE_VERSION_KEY_PREFIX}:{tenant_id}",
                time=86400,
                value="1",
            )
            return 1
        return max(int(value), 1)
    except Exception:
        return 1


async def _cache_get(
    redis_client: aioredis.Redis | None,
    *,
    key: str,
) -> dict[str, Any] | None:
    if redis_client is None:
        return None
    try:
        payload = await redis_client.get(key)
        if not payload:
            return None
        parsed = json.loads(payload)
        if isinstance(parsed, dict):
            return parsed
        return None
    except Exception:
        return None


async def _cache_set(
    redis_client: aioredis.Redis | None,
    *,
    key: str,
    payload: dict[str, Any],
) -> None:
    if redis_client is None:
        return
    try:
        await redis_client.setex(
            name=key,
            time=_CACHE_TTL_SECONDS,
            value=json.dumps(payload),
        )
    except Exception:
        return


async def _bump_cache_version(redis_client: aioredis.Redis | None, *, tenant_id: uuid.UUID) -> None:
    if redis_client is None:
        return
    try:
        await redis_client.incr(f"{_CACHE_VERSION_KEY_PREFIX}:{tenant_id}")
    except Exception:
        return


async def _cache_key_for_request(
    request: Request,
    *,
    tenant_id: uuid.UUID,
    feature: str,
    redis_client: aioredis.Redis | None,
) -> str:
    version = await _analytics_cache_version(redis_client, tenant_id=tenant_id)
    return (
        f"{_CACHE_KEY_PREFIX}:{feature}:{tenant_id}:v{version}:"
        f"{_query_signature(request)}"
    )


@router.get("/kpis")
async def get_kpis_endpoint(
    request: Request,
    org_entity_id: uuid.UUID | None = Query(default=None),
    org_group_id: uuid.UUID | None = Query(default=None),
    as_of_date: date | None = Query(default=None),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
    redis_client: aioredis.Redis = Depends(get_redis),
) -> dict[str, Any]:
    _assert_analytics_access(user)
    cache_key = await _cache_key_for_request(
        request,
        tenant_id=user.tenant_id,
        feature="kpis",
        redis_client=redis_client,
    )
    cached_payload = await _cache_get(redis_client, key=cache_key)
    if cached_payload is not None:
        return cached_payload
    payload = await compute_kpis(
        session,
        tenant_id=user.tenant_id,
        org_entity_id=org_entity_id,
        org_group_id=org_group_id,
        as_of_date=as_of_date,
        from_date=from_date,
        to_date=to_date,
    )
    metrics = {row.metric_name: row.metric_value for row in payload.rows}
    alerts = await evaluate_alerts(session, tenant_id=user.tenant_id, metrics=metrics)
    await session.commit()
    return ok(
        {
            **payload.model_dump(mode="json"),
            "alerts": [row.model_dump(mode="json") for row in alerts],
        },
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")
    await _cache_set(redis_client, key=cache_key, payload=response_payload)
    return response_payload


@router.get("/variance")
async def get_variance_endpoint(
    request: Request,
    org_entity_id: uuid.UUID | None = Query(default=None),
    org_group_id: uuid.UUID | None = Query(default=None),
    from_date: date = Query(...),
    to_date: date = Query(...),
    comparison: str = Query(default="prev_month"),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
    redis_client: aioredis.Redis = Depends(get_redis),
) -> dict[str, Any]:
    _assert_analytics_access(user)
    cache_key = await _cache_key_for_request(
        request,
        tenant_id=user.tenant_id,
        feature="variance",
        redis_client=redis_client,
    )
    cached_payload = await _cache_get(redis_client, key=cache_key)
    if cached_payload is not None:
        return cached_payload
    payload = await compute_variance(
        session,
        tenant_id=user.tenant_id,
        org_entity_id=org_entity_id,
        org_group_id=org_group_id,
        from_date=from_date,
        to_date=to_date,
        comparison=comparison,
    )
    await session.commit()
    response_payload = ok(
        payload.model_dump(mode="json"),
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")
    await _cache_set(redis_client, key=cache_key, payload=response_payload)
    return response_payload


@router.get("/trends")
async def get_trends_endpoint(
    request: Request,
    org_entity_id: uuid.UUID | None = Query(default=None),
    org_group_id: uuid.UUID | None = Query(default=None),
    from_date: date = Query(...),
    to_date: date = Query(...),
    frequency: str = Query(default="monthly"),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
    redis_client: aioredis.Redis = Depends(get_redis),
) -> dict[str, Any]:
    _assert_analytics_access(user)
    cache_key = await _cache_key_for_request(
        request,
        tenant_id=user.tenant_id,
        feature="trends",
        redis_client=redis_client,
    )
    cached_payload = await _cache_get(redis_client, key=cache_key)
    if cached_payload is not None:
        return cached_payload
    payload = await compute_trends(
        session,
        tenant_id=user.tenant_id,
        org_entity_id=org_entity_id,
        org_group_id=org_group_id,
        from_date=from_date,
        to_date=to_date,
        frequency=frequency,
    )
    await session.commit()
    response_payload = ok(
        payload.model_dump(mode="json"),
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")
    await _cache_set(redis_client, key=cache_key, payload=response_payload)
    return response_payload


@router.get("/ratios")
async def get_ratios_endpoint(
    request: Request,
    org_entity_id: uuid.UUID | None = Query(default=None),
    org_group_id: uuid.UUID | None = Query(default=None),
    as_of_date: date | None = Query(default=None),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
    redis_client: aioredis.Redis = Depends(get_redis),
) -> dict[str, Any]:
    _assert_analytics_access(user)
    cache_key = await _cache_key_for_request(
        request,
        tenant_id=user.tenant_id,
        feature="ratios",
        redis_client=redis_client,
    )
    cached_payload = await _cache_get(redis_client, key=cache_key)
    if cached_payload is not None:
        return cached_payload
    payload = await compute_ratios(
        session,
        tenant_id=user.tenant_id,
        org_entity_id=org_entity_id,
        org_group_id=org_group_id,
        as_of_date=as_of_date,
        from_date=from_date,
        to_date=to_date,
    )
    await session.commit()
    response_payload = ok(
        payload.model_dump(mode="json"),
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")
    await _cache_set(redis_client, key=cache_key, payload=response_payload)
    return response_payload


@router.get("/budget-variance")
async def get_budget_variance_endpoint(
    request: Request,
    org_entity_id: uuid.UUID = Query(...),
    period: str = Query(...),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
    redis_client: aioredis.Redis = Depends(get_redis),
) -> dict[str, Any]:
    _assert_analytics_access(user)
    cache_key = await _cache_key_for_request(
        request,
        tenant_id=user.tenant_id,
        feature="budget_variance",
        redis_client=redis_client,
    )
    cached_payload = await _cache_get(redis_client, key=cache_key)
    if cached_payload is not None:
        return cached_payload
    payload = await get_budget_variance(
        session,
        tenant_id=user.tenant_id,
        org_entity_id=org_entity_id,
        period=period,
    )
    await session.commit()
    response_payload = ok(
        payload.model_dump(mode="json"),
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")
    await _cache_set(redis_client, key=cache_key, payload=response_payload)
    return response_payload


@router.get("/drilldown")
async def get_drilldown_endpoint(
    request: Request,
    metric_name: str = Query(...),
    org_entity_id: uuid.UUID | None = Query(default=None),
    org_group_id: uuid.UUID | None = Query(default=None),
    from_date: date = Query(...),
    to_date: date = Query(...),
    as_of_date: date | None = Query(default=None),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    _assert_analytics_access(user)
    resolved_as_of = as_of_date or to_date
    payload = await get_metric_drilldown(
        session,
        tenant_id=user.tenant_id,
        metric_name=metric_name,
        org_entity_id=org_entity_id,
        org_group_id=org_group_id,
        from_date=from_date,
        to_date=to_date,
        as_of_date=resolved_as_of,
    )
    return ok(
        payload.model_dump(mode="json"),
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.post("/alerts")
async def create_alert_endpoint(
    request: Request,
    body: AlertCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
    redis_client: aioredis.Redis = Depends(get_redis),
) -> dict[str, Any]:
    _assert_analytics_access(user)
    payload = await create_alert(
        session,
        tenant_id=user.tenant_id,
        body=body,
    )
    await session.commit()
    await _bump_cache_version(redis_client, tenant_id=user.tenant_id)
    return ok(
        payload.model_dump(mode="json"),
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.get("/alerts")
async def list_alerts_endpoint(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
    redis_client: aioredis.Redis = Depends(get_redis),
) -> dict[str, Any]:
    _assert_analytics_access(user)
    cache_key = await _cache_key_for_request(
        request,
        tenant_id=user.tenant_id,
        feature="alerts",
        redis_client=redis_client,
    )
    cached_payload = await _cache_get(redis_client, key=cache_key)
    if cached_payload is not None:
        return cached_payload
    payload = await list_alerts(
        session,
        tenant_id=user.tenant_id,
        limit=limit,
        offset=offset,
    )
    response_payload = ok(
        [item.model_dump(mode="json") for item in payload],
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")
    await _cache_set(redis_client, key=cache_key, payload=response_payload)
    return response_payload


@router.get("/health")
async def analytics_health() -> dict[str, Any]:
    return {"status": "ok", "module": "analytics_layer", "version": 8}
