from __future__ import annotations

from io import BytesIO
import uuid
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from openpyxl import Workbook
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user, require_finance_leader
from financeops.core.exceptions import NotFoundError, ValidationError
from financeops.core.intent.api import build_idempotency_key, build_intent_actor
from financeops.core.intent.enums import IntentType
from financeops.core.intent.service import IntentService
from financeops.db.models.users import IamUser
from financeops.modules.forecasting.models import ForecastAssumption, ForecastLineItem, ForecastRun
from financeops.modules.forecasting.service import (
    compute_forecast_lines,
    create_forecast_run,
    get_forecast_vs_budget,
    publish_forecast,
    update_assumption,
)
from financeops.shared_kernel.pagination import Paginated

router = APIRouter(prefix="/forecast", tags=["forecasting"])


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


class CreateForecastRequest(BaseModel):
    run_name: str
    forecast_type: str
    base_period: str
    horizon_months: int


class UpdateAssumptionRequest(BaseModel):
    value: str
    basis: str | None = None


def _to_decimal(value: str, field_name: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"{field_name} must be a decimal string") from exc


def _serialize_run(row: ForecastRun) -> dict:
    return {
        "id": str(row.id),
        "tenant_id": str(row.tenant_id),
        "run_name": row.run_name,
        "forecast_type": row.forecast_type,
        "base_period": row.base_period,
        "horizon_months": row.horizon_months,
        "status": row.status,
        "is_published": row.is_published,
        "published_at": row.published_at.isoformat() if row.published_at else None,
        "published_by": str(row.published_by) if row.published_by else None,
        "created_by": str(row.created_by),
        "created_at": row.created_at.isoformat(),
    }


def _serialize_assumption(row: ForecastAssumption) -> dict:
    return {
        "id": str(row.id),
        "forecast_run_id": str(row.forecast_run_id),
        "tenant_id": str(row.tenant_id),
        "assumption_key": row.assumption_key,
        "assumption_value": format(Decimal(str(row.assumption_value)), "f"),
        "assumption_label": row.assumption_label,
        "category": row.category,
        "basis": row.basis,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


def _serialize_line(row: ForecastLineItem) -> dict:
    return {
        "id": str(row.id),
        "forecast_run_id": str(row.forecast_run_id),
        "tenant_id": str(row.tenant_id),
        "period": row.period,
        "is_actual": row.is_actual,
        "mis_line_item": row.mis_line_item,
        "mis_category": row.mis_category,
        "amount": format(Decimal(str(row.amount)), "f"),
        "entity_id": str(row.entity_id) if row.entity_id else None,
        "created_at": row.created_at.isoformat(),
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_run(
    request: Request,
    body: CreateForecastRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    try:
        result = await _submit_intent(
            request,
            session,
            user=user,
            intent_type=IntentType.CREATE_FORECAST_RUN,
            payload=body.model_dump(mode="json"),
        )
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc
    run = (
        await session.execute(
            select(ForecastRun).where(
                ForecastRun.id == uuid.UUID(str((result.record_refs or {})["run_id"])),
                ForecastRun.tenant_id == user.tenant_id,
            )
        )
    ).scalar_one()
    assumptions = (
        await session.execute(
            select(ForecastAssumption).where(
                ForecastAssumption.forecast_run_id == run.id,
                ForecastAssumption.tenant_id == user.tenant_id,
            )
        )
    ).scalars().all()
    return {
        "run": _serialize_run(run),
        "assumptions": [_serialize_assumption(row) for row in assumptions],
        "intent_id": str(result.intent_id),
        "job_id": str(result.job_id) if result.job_id else None,
    }


@router.get("")
async def list_runs(
    forecast_type: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> Paginated[dict]:
    stmt = select(ForecastRun).where(ForecastRun.tenant_id == user.tenant_id)
    if forecast_type:
        stmt = stmt.where(ForecastRun.forecast_type == forecast_type)
    if status_filter:
        stmt = stmt.where(ForecastRun.status == status_filter)

    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (
        await session.execute(
            stmt.order_by(ForecastRun.created_at.desc(), ForecastRun.id.desc()).limit(limit).offset(offset)
        )
    ).scalars().all()
    return Paginated[dict](
        data=[_serialize_run(row) for row in rows],
        total=int(total),
        limit=limit,
        offset=offset,
    )


@router.get("/{run_id}")
async def get_run(
    run_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    run = (
        await session.execute(
            select(ForecastRun).where(
                ForecastRun.id == run_id,
                ForecastRun.tenant_id == user.tenant_id,
            )
        )
    ).scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Forecast run not found")
    assumptions = (
        await session.execute(
            select(ForecastAssumption).where(
                ForecastAssumption.tenant_id == user.tenant_id,
                ForecastAssumption.forecast_run_id == run.id,
            )
        )
    ).scalars().all()
    lines = (
        await session.execute(
            select(ForecastLineItem).where(
                ForecastLineItem.tenant_id == user.tenant_id,
                ForecastLineItem.forecast_run_id == run.id,
            )
        )
    ).scalars().all()
    return {
        "run": _serialize_run(run),
        "assumptions": [_serialize_assumption(row) for row in assumptions],
        "line_items": [_serialize_line(row) for row in lines],
    }


@router.patch("/{run_id}/assumptions/{key}")
async def patch_assumption(
    request: Request,
    run_id: uuid.UUID,
    key: str,
    body: UpdateAssumptionRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    run = (
        await session.execute(
            select(ForecastRun).where(
                ForecastRun.id == run_id,
                ForecastRun.tenant_id == user.tenant_id,
            )
        )
    ).scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Forecast run not found")
    try:
        result = await _submit_intent(
            request,
            session,
            user=user,
            intent_type=IntentType.UPDATE_FORECAST_ASSUMPTION,
            payload={
                "forecast_run_id": str(run_id),
                "assumption_key": key,
                "new_value": str(_to_decimal(body.value, "value")),
                "basis": body.basis,
            },
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
    row = (
        await session.execute(
            select(ForecastAssumption).where(
                ForecastAssumption.tenant_id == user.tenant_id,
                ForecastAssumption.forecast_run_id == run_id,
                ForecastAssumption.assumption_key == key,
            )
        )
    ).scalar_one()
    lines_count = (
        await session.execute(
            select(func.count()).select_from(ForecastLineItem).where(
                ForecastLineItem.tenant_id == user.tenant_id,
                ForecastLineItem.forecast_run_id == run_id,
            )
        )
    ).scalar_one()
    return {
        "assumption": _serialize_assumption(row),
        "line_items_total": int(lines_count),
        "intent_id": str(result.intent_id),
        "job_id": str(result.job_id) if result.job_id else None,
    }


@router.post("/{run_id}/compute")
async def compute(
    request: Request,
    run_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    run = (
        await session.execute(
            select(ForecastRun).where(
                ForecastRun.id == run_id,
                ForecastRun.tenant_id == user.tenant_id,
            )
        )
    ).scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Forecast run not found")
    try:
        result = await _submit_intent(
            request,
            session,
            user=user,
            intent_type=IntentType.COMPUTE_FORECAST_LINES,
            payload={"forecast_run_id": str(run_id)},
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
    return {
        "line_items_created": int((result.record_refs or {}).get("line_items_created") or 0),
        "intent_id": str(result.intent_id),
        "job_id": str(result.job_id) if result.job_id else None,
    }


@router.post("/{run_id}/publish")
async def publish(
    request: Request,
    run_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> dict:
    existing = (
        await session.execute(
            select(ForecastRun).where(
                ForecastRun.id == run_id,
                ForecastRun.tenant_id == user.tenant_id,
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        raise HTTPException(status_code=404, detail="Forecast run not found")
    try:
        result = await _submit_intent(
            request,
            session,
            user=user,
            intent_type=IntentType.PUBLISH_FORECAST,
            payload={"forecast_run_id": str(run_id)},
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
    row = (
        await session.execute(
            select(ForecastRun).where(
                ForecastRun.id == uuid.UUID(str((result.record_refs or {})["run_id"])),
                ForecastRun.tenant_id == user.tenant_id,
            )
        )
    ).scalar_one()
    payload = _serialize_run(row)
    payload["intent_id"] = str(result.intent_id)
    payload["job_id"] = str(result.job_id) if result.job_id else None
    return payload


@router.get("/{run_id}/vs-budget")
async def vs_budget(
    run_id: uuid.UUID,
    fiscal_year: int = Query(...),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    try:
        payload = await get_forecast_vs_budget(
            session,
            tenant_id=user.tenant_id,
            forecast_run_id=run_id,
            fiscal_year=fiscal_year,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
    return {
        "forecast_run_id": payload["forecast_run_id"],
        "fiscal_year": payload["fiscal_year"],
        "rows": [
            {
                "period": row["period"],
                "mis_line_item": row["mis_line_item"],
                "budget": format(row["budget"], "f"),
                "forecast": format(row["forecast"], "f"),
                "variance": format(row["variance"], "f"),
                "variance_pct": format(row["variance_pct"], "f"),
            }
            for row in payload["rows"]
        ],
    }


@router.get("/{run_id}/export")
async def export_run(
    run_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> Response:
    run = (
        await session.execute(
            select(ForecastRun).where(
                ForecastRun.id == run_id,
                ForecastRun.tenant_id == user.tenant_id,
            )
        )
    ).scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Forecast run not found")
    lines = (
        await session.execute(
            select(ForecastLineItem)
            .where(
                ForecastLineItem.tenant_id == user.tenant_id,
                ForecastLineItem.forecast_run_id == run.id,
            )
            .order_by(ForecastLineItem.period, ForecastLineItem.mis_line_item)
        )
    ).scalars().all()

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Forecast"
    sheet.append(["Period", "Line Item", "Category", "Amount", "Is Actual"])
    for row in lines:
        sheet.append(
            [
                row.period,
                row.mis_line_item,
                row.mis_category,
                format(Decimal(str(row.amount)), "f"),
                "yes" if row.is_actual else "no",
            ]
        )

    buffer = BytesIO()
    workbook.save(buffer)
    filename = f"Forecast_{run.id}.xlsx"
    return Response(
        content=buffer.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
