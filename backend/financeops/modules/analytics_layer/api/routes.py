from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user
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
) -> dict[str, Any]:
    _assert_analytics_access(user)
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
) -> dict[str, Any]:
    _assert_analytics_access(user)
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
    return ok(
        payload.model_dump(mode="json"),
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


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
) -> dict[str, Any]:
    _assert_analytics_access(user)
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
    return ok(
        payload.model_dump(mode="json"),
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


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
) -> dict[str, Any]:
    _assert_analytics_access(user)
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
    return ok(
        payload.model_dump(mode="json"),
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.get("/budget-variance")
async def get_budget_variance_endpoint(
    request: Request,
    org_entity_id: uuid.UUID = Query(...),
    period: str = Query(...),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    _assert_analytics_access(user)
    payload = await get_budget_variance(
        session,
        tenant_id=user.tenant_id,
        org_entity_id=org_entity_id,
        period=period,
    )
    await session.commit()
    return ok(
        payload.model_dump(mode="json"),
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


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
) -> dict[str, Any]:
    _assert_analytics_access(user)
    payload = await create_alert(
        session,
        tenant_id=user.tenant_id,
        body=body,
    )
    await session.commit()
    return ok(
        payload.model_dump(mode="json"),
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.get("/alerts")
async def list_alerts_endpoint(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    _assert_analytics_access(user)
    payload = await list_alerts(session, tenant_id=user.tenant_id)
    return ok(
        [item.model_dump(mode="json") for item in payload],
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.get("/health")
async def analytics_health() -> dict[str, Any]:
    return {"status": "ok", "module": "analytics_layer", "version": 8}
