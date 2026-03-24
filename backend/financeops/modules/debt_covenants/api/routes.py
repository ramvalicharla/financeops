from __future__ import annotations

import uuid
from decimal import Decimal
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user
from financeops.db.models.users import IamUser
from financeops.modules.debt_covenants.models import CovenantBreachEvent, CovenantDefinition
from financeops.modules.debt_covenants.service import check_all_covenants, get_covenant_dashboard
from financeops.shared_kernel.pagination import Paginated

router = APIRouter(prefix="/covenants", tags=["covenants"])


class CovenantCreateRequest(BaseModel):
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
    period: str


def _decimal(value: Decimal) -> str:
    return format(Decimal(str(value)), "f")


def _serialize_definition(row: CovenantDefinition) -> dict:
    return {
        "id": str(row.id),
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
        "period": row.period,
        "actual_value": _decimal(row.actual_value),
        "threshold_value": _decimal(row.threshold_value),
        "breach_type": row.breach_type,
        "variance_pct": _decimal(row.variance_pct),
        "computed_at": row.computed_at.isoformat(),
    }


@router.get("/dashboard")
async def covenant_dashboard_endpoint(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    payload = await get_covenant_dashboard(session, tenant_id=user.tenant_id)
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
    body: CovenantCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    now = datetime.utcnow()
    row = CovenantDefinition(
        tenant_id=user.tenant_id,
        facility_name=body.facility_name,
        lender_name=body.lender_name,
        covenant_type=body.covenant_type,
        covenant_label=body.covenant_label,
        threshold_value=body.threshold_value,
        threshold_direction=body.threshold_direction,
        measurement_frequency=body.measurement_frequency,
        is_active=True,
        grace_period_days=body.grace_period_days,
        notification_threshold_pct=body.notification_threshold_pct,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    await session.flush()
    return _serialize_definition(row)


@router.patch("/{covenant_id}")
async def patch_covenant_endpoint(
    covenant_id: uuid.UUID,
    body: CovenantPatchRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    row = (
        await session.execute(
            select(CovenantDefinition).where(CovenantDefinition.id == covenant_id, CovenantDefinition.tenant_id == user.tenant_id)
        )
    ).scalar_one()
    updates = body.model_dump(exclude_none=True)
    for key, value in updates.items():
        setattr(row, key, value)
    row.updated_at = datetime.utcnow()
    await session.flush()
    return _serialize_definition(row)


@router.post("/check")
async def run_check_endpoint(
    body: CheckRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    rows = await check_all_covenants(session, tenant_id=user.tenant_id, period=body.period)
    return {"events": [_serialize_event(row) for row in rows], "count": len(rows)}


@router.get("/{covenant_id}/history", response_model=Paginated[dict])
async def history_endpoint(
    covenant_id: uuid.UUID,
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> Paginated[dict]:
    total = int(
        (
            await session.execute(
                select(func.count())
                .select_from(CovenantBreachEvent)
                .where(CovenantBreachEvent.covenant_id == covenant_id, CovenantBreachEvent.tenant_id == user.tenant_id)
            )
        ).scalar_one()
    )
    rows = (
        await session.execute(
            select(CovenantBreachEvent)
            .where(CovenantBreachEvent.covenant_id == covenant_id, CovenantBreachEvent.tenant_id == user.tenant_id)
            .order_by(desc(CovenantBreachEvent.computed_at), desc(CovenantBreachEvent.id))
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()
    return Paginated[dict](data=[_serialize_event(row) for row in rows], total=total, limit=limit, offset=offset)


__all__ = ["router"]
