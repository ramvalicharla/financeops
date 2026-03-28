from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user
from financeops.db.models.accounting_jv import AccountingJVAggregate
from financeops.db.models.users import IamUser, UserRole
from financeops.modules.accounting_layer.application.jv_service import (
    create_jv,
    get_jv,
    get_jv_state_history,
    list_jvs,
    transition_jv,
    update_jv_lines,
)
from financeops.modules.accounting_layer.domain.schemas import (
    JVCreate,
    JVLineResponse,
    JVResponse,
    JVStateEventResponse,
    JVTransitionRequest,
    JVUpdateLines,
)
from financeops.shared_kernel.response import ok

router = APIRouter(prefix="/jv", tags=["Accounting JV"])


def _is_admin(user: IamUser) -> bool:
    return user.role in {UserRole.super_admin, UserRole.finance_leader, UserRole.platform_owner}


def _serialize_jv(jv: AccountingJVAggregate) -> dict[str, Any]:
    active_lines = [line for line in jv.lines if line.jv_version == jv.version]
    base_payload = JVResponse.model_validate(jv).model_dump(mode="json")
    base_payload["lines"] = [
        JVLineResponse.model_validate(line).model_dump(mode="json")
        for line in active_lines
    ]
    return base_payload


@router.post("/")
async def create_jv_endpoint(
    request: Request,
    body: JVCreate,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    jv = await create_jv(
        session,
        tenant_id=user.tenant_id,
        entity_id=body.entity_id,
        created_by=user.id,
        period_date=body.period_date,
        fiscal_year=body.fiscal_year,
        fiscal_period=body.fiscal_period,
        description=body.description,
        reference=body.reference,
        currency=body.currency,
        location_id=body.location_id,
        cost_centre_id=body.cost_centre_id,
        workflow_instance_id=body.workflow_instance_id,
        lines=[line.model_dump() for line in body.lines] if body.lines else None,
    )
    await session.flush()
    return ok(
        _serialize_jv(jv),
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.get("/")
async def list_jvs_endpoint(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
    entity_id: uuid.UUID | None = Query(default=None),
    status: str | None = Query(default=None),
    fiscal_year: int | None = Query(default=None),
    fiscal_period: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    rows = await list_jvs(
        session,
        tenant_id=user.tenant_id,
        entity_id=entity_id,
        status=status,
        fiscal_year=fiscal_year,
        fiscal_period=fiscal_period,
        limit=limit,
        offset=offset,
    )
    payload = [_serialize_jv(row) for row in rows]
    return ok(payload, request_id=getattr(request.state, "request_id", None)).model_dump(mode="json")


@router.get("/{jv_id}")
async def get_jv_endpoint(
    request: Request,
    jv_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    jv = await get_jv(session, jv_id=jv_id, tenant_id=user.tenant_id)
    return ok(
        _serialize_jv(jv),
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.put("/{jv_id}/lines")
async def update_jv_lines_endpoint(
    request: Request,
    jv_id: uuid.UUID,
    body: JVUpdateLines,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    jv = await update_jv_lines(
        session,
        jv_id=jv_id,
        tenant_id=user.tenant_id,
        lines=[line.model_dump() for line in body.lines],
        expected_version=body.expected_version,
    )
    await session.flush()
    return ok(
        _serialize_jv(jv),
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.post("/{jv_id}/transition")
async def transition_jv_endpoint(
    request: Request,
    jv_id: uuid.UUID,
    body: JVTransitionRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    jv = await transition_jv(
        session,
        jv_id=jv_id,
        tenant_id=user.tenant_id,
        to_status=body.to_status,
        triggered_by=user.id,
        actor_role=user.role.value,
        expected_version=body.expected_version,
        comment=body.comment,
        is_admin=_is_admin(user),
    )
    await session.flush()
    return ok(
        _serialize_jv(jv),
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.get("/{jv_id}/history")
async def get_jv_history_endpoint(
    request: Request,
    jv_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    events = await get_jv_state_history(session, jv_id=jv_id, tenant_id=user.tenant_id)
    payload = [JVStateEventResponse.model_validate(event).model_dump(mode="json") for event in events]
    return ok(payload, request_id=getattr(request.state, "request_id", None)).model_dump(mode="json")
