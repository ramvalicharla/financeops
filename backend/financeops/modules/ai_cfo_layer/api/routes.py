from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user
from financeops.core.exceptions import AuthorizationError
from financeops.db.models.users import IamUser, UserRole
from financeops.modules.ai_cfo_layer.application.anomaly_service import detect_anomalies
from financeops.modules.ai_cfo_layer.application.audit_sampling_service import (
    get_audit_samples,
)
from financeops.modules.ai_cfo_layer.application.explanation_service import (
    explain_variance,
)
from financeops.modules.ai_cfo_layer.application.narrative_service import (
    generate_narrative,
)
from financeops.modules.ai_cfo_layer.application.recommendation_service import (
    generate_recommendations,
)
from financeops.modules.ai_cfo_layer.application.suggestion_service import (
    generate_journal_suggestions,
)
from financeops.shared_kernel.response import ok

router = APIRouter(prefix="/ai", tags=["AI CFO"])

_ALLOWED_ROLES = {
    UserRole.super_admin,
    UserRole.platform_owner,
    UserRole.platform_admin,
    UserRole.finance_leader,
    UserRole.finance_team,
    UserRole.auditor,
    UserRole.read_only,
}


def _assert_access(user: IamUser) -> None:
    if user.role not in _ALLOWED_ROLES:
        raise AuthorizationError("AI CFO access requires finance/admin role.")


def _default_window() -> tuple[date, date]:
    to_date = date.today()
    return to_date - timedelta(days=30), to_date


@router.get("/anomalies")
async def anomalies_endpoint(
    request: Request,
    org_entity_id: uuid.UUID | None = Query(default=None),
    org_group_id: uuid.UUID | None = Query(default=None),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    comparison: str = Query(default="prev_month"),
    db: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    _assert_access(user)
    if from_date is None or to_date is None:
        from_date, to_date = _default_window()
    payload = await detect_anomalies(
        db,
        tenant_id=user.tenant_id,
        actor_user_id=user.id,
        org_entity_id=org_entity_id,
        org_group_id=org_group_id,
        from_date=from_date,
        to_date=to_date,
        comparison=comparison,
    )
    await db.commit()
    return ok(payload.model_dump(mode="json"), request_id=getattr(request.state, "request_id", None)).model_dump(mode="json")


@router.get("/explain-variance")
async def explain_variance_endpoint(
    request: Request,
    metric_name: str = Query(...),
    org_entity_id: uuid.UUID | None = Query(default=None),
    org_group_id: uuid.UUID | None = Query(default=None),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    comparison: str = Query(default="prev_month"),
    db: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    _assert_access(user)
    if from_date is None or to_date is None:
        from_date, to_date = _default_window()
    payload = await explain_variance(
        db,
        tenant_id=user.tenant_id,
        metric_name=metric_name,
        org_entity_id=org_entity_id,
        org_group_id=org_group_id,
        from_date=from_date,
        to_date=to_date,
        comparison=comparison,
    )
    await db.commit()
    return ok(payload.model_dump(mode="json"), request_id=getattr(request.state, "request_id", None)).model_dump(mode="json")


@router.get("/recommendations")
async def recommendations_endpoint(
    request: Request,
    org_entity_id: uuid.UUID | None = Query(default=None),
    org_group_id: uuid.UUID | None = Query(default=None),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    comparison: str = Query(default="prev_month"),
    db: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    _assert_access(user)
    if from_date is None or to_date is None:
        from_date, to_date = _default_window()
    payload = await generate_recommendations(
        db,
        tenant_id=user.tenant_id,
        actor_user_id=user.id,
        org_entity_id=org_entity_id,
        org_group_id=org_group_id,
        from_date=from_date,
        to_date=to_date,
        comparison=comparison,
    )
    await db.commit()
    return ok(payload.model_dump(mode="json"), request_id=getattr(request.state, "request_id", None)).model_dump(mode="json")


@router.get("/narrative")
async def narrative_endpoint(
    request: Request,
    org_entity_id: uuid.UUID | None = Query(default=None),
    org_group_id: uuid.UUID | None = Query(default=None),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    comparison: str = Query(default="prev_month"),
    db: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    _assert_access(user)
    if from_date is None or to_date is None:
        from_date, to_date = _default_window()
    payload = await generate_narrative(
        db,
        tenant_id=user.tenant_id,
        actor_user_id=user.id,
        org_entity_id=org_entity_id,
        org_group_id=org_group_id,
        from_date=from_date,
        to_date=to_date,
        comparison=comparison,
    )
    await db.commit()
    return ok(payload.model_dump(mode="json"), request_id=getattr(request.state, "request_id", None)).model_dump(mode="json")


@router.get("/suggestions")
async def suggestions_endpoint(
    request: Request,
    org_entity_id: uuid.UUID | None = Query(default=None),
    org_group_id: uuid.UUID | None = Query(default=None),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    db: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    _assert_access(user)
    if from_date is None or to_date is None:
        from_date, to_date = _default_window()
    payload = await generate_journal_suggestions(
        db,
        tenant_id=user.tenant_id,
        org_entity_id=org_entity_id,
        org_group_id=org_group_id,
        from_date=from_date,
        to_date=to_date,
    )
    await db.commit()
    return ok(payload.model_dump(mode="json"), request_id=getattr(request.state, "request_id", None)).model_dump(mode="json")


@router.get("/audit-samples")
async def audit_samples_endpoint(
    request: Request,
    org_entity_id: uuid.UUID | None = Query(default=None),
    org_group_id: uuid.UUID | None = Query(default=None),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    mode: str = Query(default="risk_based"),
    sample_size: int = Query(default=25, ge=1, le=250),
    db: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    _assert_access(user)
    if from_date is None or to_date is None:
        from_date, to_date = _default_window()
    payload = await get_audit_samples(
        db,
        tenant_id=user.tenant_id,
        org_entity_id=org_entity_id,
        org_group_id=org_group_id,
        from_date=from_date,
        to_date=to_date,
        mode=mode,
        sample_size=sample_size,
    )
    return ok(payload.model_dump(mode="json"), request_id=getattr(request.state, "request_id", None)).model_dump(mode="json")

