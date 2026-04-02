from __future__ import annotations

import uuid
from datetime import date, timedelta

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import (
    get_async_session,
    get_redis,
    require_finance_leader,
    require_finance_team,
)
from financeops.config import settings
from financeops.db.models.users import IamUser
from financeops.schemas.fx_rates import (
    ApplyMonthEndRequest,
    ApplyMonthEndResponse,
    CompareRatesResponse,
    ConvertDailyRequest,
    ConvertDailyResponse,
    FetchLiveRatesRequest,
    FetchLiveRatesResponse,
    FxRateCreateRequest,
    FxRateListResponse,
    FxRateRecord,
    FxVarianceRequest,
    FxVarianceResponse,
    ManualMonthlyRateCreateRequest,
    ManualMonthlyRateListResponse,
)
from financeops.services.fx import (
    create_fx_rate,
    compute_and_store_variance,
    convert_daily_lines,
    get_latest_fx_rate,
    create_manual_monthly_rate,
    get_required_latest_comparison,
    list_fx_rates,
    list_manual_monthly_rates,
)
from financeops.temporal.client import get_temporal_client
from financeops.temporal.fx_workflows import (
    FxFetchWorkflow,
    FxFetchWorkflowInput,
    FxMonthEndApplyWorkflow,
    FxMonthEndApplyWorkflowInput,
)

router = APIRouter()


@router.post("/rates", response_model=FxRateRecord, status_code=status.HTTP_201_CREATED)
async def create_fx_rate_endpoint(
    body: FxRateCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> dict:
    row = await create_fx_rate(
        session,
        tenant_id=None if body.is_global else user.tenant_id,
        from_currency=body.from_currency,
        to_currency=body.to_currency,
        rate=body.rate,
        rate_type=body.rate_type,
        effective_date=body.effective_date,
        source=body.source,
        created_by=user.id,
    )
    await session.flush()
    return {
        "id": str(row.id),
        "tenant_id": str(row.tenant_id) if row.tenant_id else None,
        "from_currency": row.from_currency,
        "to_currency": row.to_currency,
        "rate": str(row.rate),
        "rate_type": row.rate_type,
        "effective_date": row.effective_date.isoformat(),
        "source": row.source,
        "created_by": str(row.created_by) if row.created_by else None,
        "created_at": row.created_at.isoformat(),
    }


@router.get("/rates", response_model=FxRateListResponse)
async def list_fx_rates_endpoint(
    from_currency: str | None = None,
    to_currency: str | None = None,
    rate_type: str | None = None,
    effective_date: date | None = None,
    limit: int = 200,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict:
    rows = await list_fx_rates(
        session,
        tenant_id=user.tenant_id,
        from_currency=from_currency,
        to_currency=to_currency,
        rate_type=rate_type,
        effective_date=effective_date,
        limit=limit,
    )
    return {
        "rates": [
            {
                "id": str(row.id),
                "tenant_id": str(row.tenant_id) if row.tenant_id else None,
                "from_currency": row.from_currency,
                "to_currency": row.to_currency,
                "rate": str(row.rate),
                "rate_type": row.rate_type,
                "effective_date": row.effective_date.isoformat(),
                "source": row.source,
                "created_by": str(row.created_by) if row.created_by else None,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ],
        "count": len(rows),
    }


@router.get("/rates/latest", response_model=FxRateRecord)
async def get_latest_fx_rate_endpoint(
    from_currency: str,
    to_currency: str,
    rate_type: str = "SPOT",
    as_of_date: date | None = None,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict:
    today = as_of_date or date.today()
    row = await get_latest_fx_rate(
        session,
        tenant_id=user.tenant_id,
        from_currency=from_currency,
        to_currency=to_currency,
        rate_type=rate_type,
        as_of_date=today,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="FX rate not found")
    return {
        "id": str(row.id),
        "tenant_id": str(row.tenant_id) if row.tenant_id else None,
        "from_currency": row.from_currency,
        "to_currency": row.to_currency,
        "rate": str(row.rate),
        "rate_type": row.rate_type,
        "effective_date": row.effective_date.isoformat(),
        "source": row.source,
        "created_by": str(row.created_by) if row.created_by else None,
        "created_at": row.created_at.isoformat(),
    }


@router.post("/fetch-live", response_model=FetchLiveRatesResponse, status_code=status.HTTP_201_CREATED)
async def fetch_live_rates_endpoint(
    body: FetchLiveRatesRequest,
    request: Request,
    user: IamUser = Depends(require_finance_team),
) -> dict:
    correlation_id = str(getattr(request.state, "correlation_id", "") or "")
    workflow_input = FxFetchWorkflowInput(
        tenant_id=str(user.tenant_id),
        requested_by=str(user.id),
        correlation_id=correlation_id,
        base_currency=body.base_currency,
        quote_currency=body.quote_currency,
        rate_date=(body.rate_date.isoformat() if body.rate_date else None),
    )
    temporal_client = await get_temporal_client()
    workflow_id = f"fx-fetch-{uuid.uuid4()}"
    result = await temporal_client.execute_workflow(
        FxFetchWorkflow.run,
        workflow_input,
        id=workflow_id,
        task_queue=settings.TEMPORAL_TASK_QUEUE,
        run_timeout=timedelta(seconds=90),
    )
    return result


@router.get("/compare", response_model=CompareRatesResponse)
async def compare_rates_endpoint(
    base_currency: str,
    quote_currency: str,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict:
    comparison = await get_required_latest_comparison(
        session,
        tenant_id=user.tenant_id,
        base_currency=base_currency,
        quote_currency=quote_currency,
    )
    return {"comparison": comparison}


@router.post(
    "/manual-monthly",
    response_model=ManualMonthlyRateListResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_manual_monthly_rate_endpoint(
    body: ManualMonthlyRateCreateRequest,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    redis_client: aioredis.Redis = Depends(get_redis),
    user: IamUser = Depends(require_finance_leader),
) -> dict:
    correlation_id = str(getattr(request.state, "correlation_id", "") or "")
    record = await create_manual_monthly_rate(
        session,
        tenant_id=user.tenant_id,
        entered_by=user.id,
        correlation_id=correlation_id,
        period_year=body.period_year,
        period_month=body.period_month,
        base_currency=body.base_currency,
        quote_currency=body.quote_currency,
        rate=body.rate,
        reason=body.reason,
        supersedes_rate_id=body.supersedes_rate_id,
        redis_client=redis_client,
    )
    await session.flush()
    return {
        "rates": [
            {
                "rate_id": str(record.id),
                "period_year": record.period_year,
                "period_month": record.period_month,
                "base_currency": record.base_currency,
                "quote_currency": record.quote_currency,
                "rate": str(record.rate),
                "reason": record.reason,
                "supersedes_rate_id": (
                    str(record.supersedes_rate_id)
                    if record.supersedes_rate_id is not None
                    else None
                ),
                "source_type": record.source_type,
                "is_month_end_locked": record.is_month_end_locked,
                "created_at": record.created_at.isoformat(),
            }
        ],
        "count": 1,
    }


@router.get("/manual-monthly", response_model=ManualMonthlyRateListResponse)
async def list_manual_monthly_rates_endpoint(
    period_year: int | None = None,
    period_month: int | None = None,
    base_currency: str | None = None,
    quote_currency: str | None = None,
    limit: int = 200,
    offset: int = 0,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict:
    rows = await list_manual_monthly_rates(
        session,
        tenant_id=user.tenant_id,
        period_year=period_year,
        period_month=period_month,
        base_currency=base_currency,
        quote_currency=quote_currency,
        limit=limit,
        offset=offset,
    )
    return {
        "rates": [
            {
                "rate_id": str(row.id),
                "period_year": row.period_year,
                "period_month": row.period_month,
                "base_currency": row.base_currency,
                "quote_currency": row.quote_currency,
                "rate": str(row.rate),
                "reason": row.reason,
                "supersedes_rate_id": (
                    str(row.supersedes_rate_id)
                    if row.supersedes_rate_id is not None
                    else None
                ),
                "source_type": row.source_type,
                "is_month_end_locked": row.is_month_end_locked,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ],
        "count": len(rows),
    }


@router.post("/convert-daily", response_model=ConvertDailyResponse)
async def convert_daily_endpoint(
    body: ConvertDailyRequest,
    session: AsyncSession = Depends(get_async_session),
    redis_client: aioredis.Redis = Depends(get_redis),
    user: IamUser = Depends(require_finance_team),
) -> dict:
    lines = await convert_daily_lines(
        session,
        tenant_id=user.tenant_id,
        lines=[line.model_dump() for line in body.lines],
        redis_client=redis_client,
    )
    return {"lines": lines, "count": len(lines)}


@router.post(
    "/apply-month-end",
    response_model=ApplyMonthEndResponse,
    status_code=status.HTTP_201_CREATED,
)
async def apply_month_end_endpoint(
    body: ApplyMonthEndRequest,
    request: Request,
    user: IamUser = Depends(require_finance_leader),
) -> dict:
    correlation_id = str(getattr(request.state, "correlation_id", "") or "")
    workflow_input = FxMonthEndApplyWorkflowInput(
        tenant_id=str(user.tenant_id),
        user_id=str(user.id),
        correlation_id=correlation_id,
        period_year=body.period_year,
        period_month=body.period_month,
        base_currency=body.base_currency,
        quote_currency=body.quote_currency,
        lines=[line.model_dump() for line in body.lines],
        approval_reason=body.approval_reason,
    )
    temporal_client = await get_temporal_client()
    workflow_id = f"fx-month-end-{uuid.uuid4()}"
    result = await temporal_client.execute_workflow(
        FxMonthEndApplyWorkflow.run,
        workflow_input,
        id=workflow_id,
        task_queue=settings.TEMPORAL_TASK_QUEUE,
        run_timeout=timedelta(seconds=120),
    )
    return result


@router.post("/variance", response_model=FxVarianceResponse, status_code=status.HTTP_201_CREATED)
async def compute_variance_endpoint(
    body: FxVarianceRequest,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict:
    correlation_id = str(getattr(request.state, "correlation_id", "") or "")
    variance = await compute_and_store_variance(
        session,
        tenant_id=user.tenant_id,
        computed_by=user.id,
        correlation_id=correlation_id,
        period_year=body.period_year,
        period_month=body.period_month,
        base_currency=body.base_currency,
        quote_currency=body.quote_currency,
        expected_difference=body.expected_difference,
        actual_difference=body.actual_difference,
        entity_name=body.entity_name,
        notes=body.notes,
    )
    await session.flush()
    return {
        "variance_id": str(variance.id),
        "period_year": variance.period_year,
        "period_month": variance.period_month,
        "base_currency": variance.base_currency,
        "quote_currency": variance.quote_currency,
        "expected_difference": str(variance.expected_difference),
        "actual_difference": str(variance.actual_difference),
        "fx_variance": str(variance.fx_variance),
        "created_at": variance.created_at.isoformat(),
    }
