from __future__ import annotations

import uuid
from decimal import Decimal
from datetime import date

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user, require_finance_leader
from financeops.db.models.users import IamUser
from financeops.modules.cash_flow_forecast.models import CashFlowForecastAssumption, CashFlowForecastRun
from financeops.modules.cash_flow_forecast.service import (
    create_forecast_run,
    get_forecast_summary,
    publish_forecast,
    seed_from_historical,
    update_week_assumptions,
)
from financeops.shared_kernel.pagination import Paginated

router = APIRouter(prefix="/treasury", tags=["treasury"])


class CreateForecastRequest(BaseModel):
    run_name: str
    base_date: date
    opening_cash_balance: Decimal
    currency: str = "INR"
    weeks: int = 13
    seed_historical: bool = True


class UpdateWeekRequest(BaseModel):
    customer_collections: Decimal | None = None
    other_inflows: Decimal | None = None
    supplier_payments: Decimal | None = None
    payroll: Decimal | None = None
    rent_and_utilities: Decimal | None = None
    loan_repayments: Decimal | None = None
    tax_payments: Decimal | None = None
    capex: Decimal | None = None
    other_outflows: Decimal | None = None
    notes: str | None = None


class PublishResponse(BaseModel):
    id: str
    status: str
    is_published: bool


def _decimal(value: Decimal) -> str:
    return format(Decimal(str(value)), "f")


def _serialize_run(row: CashFlowForecastRun) -> dict:
    return {
        "id": str(row.id),
        "tenant_id": str(row.tenant_id),
        "run_name": row.run_name,
        "base_date": row.base_date.isoformat(),
        "weeks": row.weeks,
        "opening_cash_balance": _decimal(row.opening_cash_balance),
        "currency": row.currency,
        "status": row.status,
        "is_published": row.is_published,
        "created_by": str(row.created_by),
        "created_at": row.created_at.isoformat(),
    }


def _serialize_week(row: CashFlowForecastAssumption) -> dict:
    return {
        "id": str(row.id),
        "forecast_run_id": str(row.forecast_run_id),
        "week_number": row.week_number,
        "week_start_date": row.week_start_date.isoformat(),
        "customer_collections": _decimal(row.customer_collections),
        "other_inflows": _decimal(row.other_inflows),
        "supplier_payments": _decimal(row.supplier_payments),
        "payroll": _decimal(row.payroll),
        "rent_and_utilities": _decimal(row.rent_and_utilities),
        "loan_repayments": _decimal(row.loan_repayments),
        "tax_payments": _decimal(row.tax_payments),
        "capex": _decimal(row.capex),
        "other_outflows": _decimal(row.other_outflows),
        "total_inflows": _decimal(row.total_inflows),
        "total_outflows": _decimal(row.total_outflows),
        "net_cash_flow": _decimal(row.net_cash_flow),
        "closing_balance": _decimal(row.closing_balance),
        "notes": row.notes,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


@router.post("/forecasts")
async def create_forecast_endpoint(
    body: CreateForecastRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    run = await create_forecast_run(
        session=session,
        tenant_id=user.tenant_id,
        run_name=body.run_name,
        base_date=body.base_date,
        opening_cash_balance=body.opening_cash_balance,
        currency=body.currency,
        created_by=user.id,
        weeks=body.weeks,
    )
    if body.seed_historical:
        await seed_from_historical(session, user.tenant_id, run.id)
    summary = await get_forecast_summary(session, user.tenant_id, run.id)
    return {
        "run": _serialize_run(run),
        "summary": {
            "closing_balance_week_13": _decimal(summary["closing_balance_week_13"]),
            "minimum_balance": _decimal(summary["minimum_balance"]),
            "minimum_balance_week": summary["minimum_balance_week"],
            "is_cash_positive": summary["is_cash_positive"],
        },
    }


@router.get("/forecasts", response_model=Paginated[dict])
async def list_forecasts_endpoint(
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> Paginated[dict]:
    total = int(
        (
            await session.execute(
                select(func.count())
                .select_from(CashFlowForecastRun)
                .where(CashFlowForecastRun.tenant_id == user.tenant_id)
            )
        ).scalar_one()
    )
    rows = (
        await session.execute(
            select(CashFlowForecastRun)
            .where(CashFlowForecastRun.tenant_id == user.tenant_id)
            .order_by(desc(CashFlowForecastRun.created_at), desc(CashFlowForecastRun.id))
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()
    return Paginated[dict](
        data=[_serialize_run(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/forecasts/{forecast_id}")
async def get_forecast_endpoint(
    forecast_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    summary = await get_forecast_summary(session, user.tenant_id, forecast_id)
    return {
        "run": _serialize_run(summary["run"]),
        "weeks": [_serialize_week(row) for row in summary["weeks"]],
        "opening_balance": _decimal(summary["opening_balance"]),
        "closing_balance_week_13": _decimal(summary["closing_balance_week_13"]),
        "minimum_balance": _decimal(summary["minimum_balance"]),
        "minimum_balance_week": summary["minimum_balance_week"],
        "total_inflows": _decimal(summary["total_inflows"]),
        "total_outflows": _decimal(summary["total_outflows"]),
        "net_position": _decimal(summary["net_position"]),
        "is_cash_positive": summary["is_cash_positive"],
        "weeks_below_zero": summary["weeks_below_zero"],
    }


@router.patch("/forecasts/{forecast_id}/weeks/{week_number}")
async def update_week_endpoint(
    forecast_id: uuid.UUID,
    week_number: int,
    body: UpdateWeekRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    row = await update_week_assumptions(
        session,
        tenant_id=user.tenant_id,
        forecast_run_id=forecast_id,
        week_number=week_number,
        assumption_updates=body.model_dump(exclude_none=True),
    )
    return _serialize_week(row)


@router.post("/forecasts/{forecast_id}/publish")
async def publish_forecast_endpoint(
    forecast_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> PublishResponse:
    row = await publish_forecast(session, tenant_id=user.tenant_id, forecast_run_id=forecast_id)
    return PublishResponse(id=str(row.id), status=row.status, is_published=row.is_published)


__all__ = ["router"]
