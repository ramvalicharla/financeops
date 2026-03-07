from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

import redis.asyncio as aioredis
from temporalio import activity

from financeops.config import settings
from financeops.db.session import tenant_session
from financeops.services.fx.fx_rate_service import (
    apply_month_end_rate,
    fetch_live_rates,
)
from financeops.temporal.fx_workflows import (
    FxFetchWorkflowInput,
    FxMonthEndApplyWorkflowInput,
)

_redis_client: aioredis.Redis | None = None


async def _get_redis_client() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            str(settings.REDIS_URL),
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_client


@activity.defn(name="fx_fetch_activity")
async def fx_fetch_activity(payload: FxFetchWorkflowInput) -> dict[str, Any]:
    tenant_id = uuid.UUID(payload.tenant_id)
    requested_by = uuid.UUID(payload.requested_by)
    selected_date = date.fromisoformat(payload.rate_date) if payload.rate_date else date.today()
    redis_client = await _get_redis_client()

    activity.logger.info(
        "FX fetch activity started tenant=%s corr=%s",
        str(tenant_id)[:8],
        payload.correlation_id,
    )
    async with tenant_session(tenant_id) as session:
        result = await fetch_live_rates(
            session,
            tenant_id=tenant_id,
            requested_by=requested_by,
            correlation_id=payload.correlation_id,
            base_currency=payload.base_currency,
            quote_currency=payload.quote_currency,
            rate_date=selected_date,
            redis_client=redis_client,
        )
        await session.commit()
        return result


@activity.defn(name="fx_month_end_apply_activity")
async def fx_month_end_apply_activity(payload: FxMonthEndApplyWorkflowInput) -> dict[str, Any]:
    tenant_id = uuid.UUID(payload.tenant_id)
    user_id = uuid.UUID(payload.user_id)
    redis_client = await _get_redis_client()

    line_items = [
        (line.get("reference"), Decimal(str(line["amount"])))
        for line in payload.lines
    ]
    activity.logger.info(
        "FX month-end apply activity started tenant=%s period=%d/%d corr=%s",
        str(tenant_id)[:8],
        payload.period_year,
        payload.period_month,
        payload.correlation_id,
    )
    async with tenant_session(tenant_id) as session:
        result = await apply_month_end_rate(
            session,
            tenant_id=tenant_id,
            user_id=user_id,
            correlation_id=payload.correlation_id,
            period_year=payload.period_year,
            period_month=payload.period_month,
            base_currency=payload.base_currency,
            quote_currency=payload.quote_currency,
            line_items=line_items,
            approval_reason=payload.approval_reason,
            redis_client=redis_client,
        )
        await session.commit()
        return result
