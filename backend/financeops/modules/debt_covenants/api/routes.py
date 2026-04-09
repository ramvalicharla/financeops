from __future__ import annotations

import uuid
from decimal import Decimal
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user
from financeops.core.exceptions import ValidationError
from financeops.core.intent.api import build_idempotency_key, build_intent_actor
from financeops.core.intent.enums import IntentType
from financeops.core.intent.service import IntentService
from financeops.db.models.users import IamUser
from financeops.modules.debt_covenants.models import CovenantBreachEvent, CovenantDefinition
from financeops.modules.debt_covenants.service import get_covenant_dashboard
from financeops.platform.services.tenancy.entity_access import assert_entity_access, get_entities_for_user
from financeops.shared_kernel.pagination import Paginated

router = APIRouter(prefix="/covenants", tags=["covenants"])


async def _submit_intent(
    request: Request,
    session: AsyncSession,
    *,
    user: IamUser,
    intent_type: IntentType,
    payload: dict,
    target_id: uuid.UUID | None = None,
):
    return await IntentService(session).submit_intent(
        intent_type=intent_type,
        actor=build_intent_actor(request, user),
        payload=payload,
        idempotency_key=build_idempotency_key(
            request,
            intent_type=intent_type,
            actor=user,
            body=payload,
            target_id=target_id,
        ),
        target_id=target_id,
    )


class CovenantCreateRequest(BaseModel):
    entity_id: uuid.UUID | None = None
    facility_name: str
    lender_name: str
    covenant_type: str
    covenant_label: str
    threshold_value: Decimal
    threshold_direction: str
    measurement_frequency: str = "monthly"
    grace_period_days: int = 0
    notification_threshold_pct: Decimal = Decimal("90.00")


class CovenantPatchRequest(BaseModel):
    threshold_value: Decimal | None = None
    threshold_direction: str | None = None
    measurement_frequency: str | None = None
    is_active: bool | None = None
    grace_period_days: int | None = None
    notification_threshold_pct: Decimal | None = None


class CheckRequest(BaseModel):
    entity_id: uuid.UUID | None = None
    period: str


def _decimal(value: Decimal) -> str:
    return format(Decimal(str(value)), "f")


async def _resolve_entity_id(
    session: AsyncSession,
    user: IamUser,
    entity_id: uuid.UUID | None,
) -> uuid.UUID:
    if entity_id is not None:
        return entity_id
    entities = await get_entities_for_user(
        session=session,
        tenant_id=user.tenant_id,
        user_id=user.id,
        user_role=user.role,
    )
    if entities:
        return entities[0].id
    raise HTTPException(
        status_code=422,
        detail="entity_id is required because no entity is configured for this user",
    )


def _serialize_definition(row: CovenantDefinition) -> dict:
    return {
        "id": str(row.id),
        "entity_id": str(row.entity_id),
        "facility_name": row.facility_name,
        "lender_name": row.lender_name,
        "covenant_type": row.covenant_type,
        "covenant_label": row.covenant_label,
        "threshold_value": _decimal(row.threshold_value),
        "threshold_direction": row.threshold_direction,
        "measurement_frequency": row.measurement_frequency,
        "is_active": row.is_active,
        "grace_period_days": row.grace_period_days,
        "notification_threshold_pct": _decimal(row.notification_threshold_pct),
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


def _serialize_event(row: CovenantBreachEvent) -> dict:
    return {
        "id": str(row.id),
        "covenant_id": str(row.covenant_id),
        "tenant_id": str(row.tenant_id),
        "entity_id": str(row.entity_id),
        "period": row.period,
        "actual_value": _decimal(row.actual_value),
        "threshold_value": _decimal(row.threshold_value),
        "breach_type": row.breach_type,
        "variance_pct": _decimal(row.variance_pct),
        "computed_at": row.computed_at.isoformat(),
    }


@router.get("/dashboard")
async def covenant_dashboard_endpoint(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    await assert_entity_access(session, user.tenant_id, entity_id, user.id, user.role)
    payload = await get_covenant_dashboard(session, tenant_id=user.tenant_id, entity_id=entity_id)
    return {
        "total_covenants": payload["total_covenants"],
        "passing": payload["passing"],
        "near_breach": payload["near_breach"],
        "breached": payload["breached"],
        "covenants": [
            {
                "definition": _serialize_definition(item["definition"]),
                "latest_event": _serialize_event(item["latest_event"]) if item["latest_event"] else None,
                "trend": item["trend"],
                "headroom_pct": _decimal(item["headroom_pct"]),
            }
            for item in payload["covenants"]
        ],
    }


@router.post("")
async def create_covenant_endpoint(
    request: Request,
    body: CovenantCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    resolved_entity_id = await _resolve_entity_id(session, user, body.entity_id)
    await assert_entity_access(session, user.tenant_id, resolved_entity_id, user.id, user.role)
    try:
        result = await _submit_intent(
            request,
            session,
            user=user,
            intent_type=IntentType.CREATE_COVENANT_DEFINITION,
            payload={
                **body.model_dump(mode="json"),
                "entity_id": str(resolved_entity_id),
            },
        )
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc
    row = (
        await session.execute(
            select(CovenantDefinition).where(
                CovenantDefinition.id == uuid.UUID(str((result.record_refs or {})["covenant_id"])),
                CovenantDefinition.tenant_id == user.tenant_id,
            )
        )
    ).scalar_one()
    payload = _serialize_definition(row)
    payload["intent_id"] = str(result.intent_id)
    payload["job_id"] = str(result.job_id) if result.job_id else None
    return payload


@router.patch("/{covenant_id}")
async def patch_covenant_endpoint(
    request: Request,
    covenant_id: uuid.UUID,
    body: CovenantPatchRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    row = (
        await session.execute(
            select(CovenantDefinition).where(CovenantDefinition.id == covenant_id, CovenantDefinition.tenant_id == user.tenant_id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Covenant not found")
    await assert_entity_access(session, user.tenant_id, row.entity_id, user.id, user.role)
    updates = body.model_dump(mode="json", exclude_none=True)
    try:
        result = await _submit_intent(
            request,
            session,
            user=user,
            intent_type=IntentType.UPDATE_COVENANT_DEFINITION,
            payload={
                "covenant_id": str(covenant_id),
                "updates": updates,
            },
        )
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc
    updated = (
        await session.execute(
            select(CovenantDefinition).where(
                CovenantDefinition.id == covenant_id,
                CovenantDefinition.tenant_id == user.tenant_id,
            )
        )
    ).scalar_one()
    payload = _serialize_definition(updated)
    payload["intent_id"] = str(result.intent_id)
    payload["job_id"] = str(result.job_id) if result.job_id else None
    return payload


@router.post("/check")
async def run_check_endpoint(
    request: Request,
    body: CheckRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    resolved_entity_id = await _resolve_entity_id(session, user, body.entity_id)
    await assert_entity_access(session, user.tenant_id, resolved_entity_id, user.id, user.role)
    try:
        result = await _submit_intent(
            request,
            session,
            user=user,
            intent_type=IntentType.CHECK_COVENANTS,
            payload={
                "entity_id": str(resolved_entity_id),
                "period": body.period,
            },
        )
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc
    event_ids = [uuid.UUID(str(value)) for value in ((result.record_refs or {}).get("event_ids") or [])]
    rows = (
        await session.execute(
            select(CovenantBreachEvent)
            .where(
                CovenantBreachEvent.id.in_(event_ids or [uuid.UUID("00000000-0000-0000-0000-000000000000")]),
                CovenantBreachEvent.tenant_id == user.tenant_id,
                CovenantBreachEvent.entity_id == resolved_entity_id,
            )
            .order_by(desc(CovenantBreachEvent.computed_at), desc(CovenantBreachEvent.id))
        )
    ).scalars().all()
    return {
        "events": [_serialize_event(row) for row in rows],
        "count": len(rows),
        "intent_id": str(result.intent_id),
        "job_id": str(result.job_id) if result.job_id else None,
    }


@router.get("/{covenant_id}/history", response_model=Paginated[dict])
async def history_endpoint(
    covenant_id: uuid.UUID,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int | None = Query(default=None, ge=0),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> Paginated[dict]:
    effective_skip = offset if offset is not None else skip
    definition = (
        await session.execute(
            select(CovenantDefinition).where(
                CovenantDefinition.id == covenant_id,
                CovenantDefinition.tenant_id == user.tenant_id,
            )
        )
    ).scalar_one_or_none()
    if definition is None:
        raise HTTPException(status_code=404, detail="Covenant not found")
    await assert_entity_access(session, user.tenant_id, definition.entity_id, user.id, user.role)
    total = int(
        (
            await session.execute(
                select(func.count())
                .select_from(CovenantBreachEvent)
                .where(
                    CovenantBreachEvent.covenant_id == covenant_id,
                    CovenantBreachEvent.tenant_id == user.tenant_id,
                    CovenantBreachEvent.entity_id == definition.entity_id,
                )
            )
        ).scalar_one()
    )
    rows = (
        await session.execute(
            select(CovenantBreachEvent)
            .where(
                CovenantBreachEvent.covenant_id == covenant_id,
                CovenantBreachEvent.tenant_id == user.tenant_id,
                CovenantBreachEvent.entity_id == definition.entity_id,
            )
            .order_by(desc(CovenantBreachEvent.computed_at), desc(CovenantBreachEvent.id))
            .limit(limit)
            .offset(effective_skip)
        )
    ).scalars().all()
    items = [_serialize_event(row) for row in rows]
    return Paginated[dict](
        items=items,
        total=total,
        limit=limit,
        skip=effective_skip,
        has_more=(effective_skip + len(items)) < total,
    )


__all__ = ["router"]
