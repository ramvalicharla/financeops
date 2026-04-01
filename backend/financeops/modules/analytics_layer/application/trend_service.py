from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from financeops.modules.accounting_layer.application.financial_statements_service import (
    get_cash_flow_statement,
    get_profit_and_loss,
)
from financeops.modules.analytics_layer.application.common import create_snapshot, resolve_scope
from financeops.modules.analytics_layer.schemas import TrendPoint, TrendResponse, TrendSeries

_ZERO = Decimal("0")


def _month_start(value: date) -> date:
    return date(value.year, value.month, 1)


def _month_end(value: date) -> date:
    if value.month == 12:
        return date(value.year + 1, 1, 1) - timedelta(days=1)
    return date(value.year, value.month + 1, 1) - timedelta(days=1)


def _quarter_start(value: date) -> date:
    quarter = ((value.month - 1) // 3) * 3 + 1
    return date(value.year, quarter, 1)


def _next_period_start(value: date, frequency: str) -> date:
    if frequency == "quarterly":
        month = value.month + 3
        year = value.year + (month - 1) // 12
        month = ((month - 1) % 12) + 1
        return date(year, month, 1)
    month = value.month + 1
    year = value.year + (month - 1) // 12
    month = ((month - 1) % 12) + 1
    return date(year, month, 1)


async def compute_trends(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    org_entity_id: uuid.UUID | None,
    org_group_id: uuid.UUID | None,
    from_date: date,
    to_date: date,
    frequency: str = "monthly",
) -> TrendResponse:
    if frequency not in {"monthly", "quarterly"}:
        raise ValueError("frequency must be monthly or quarterly")

    scope = await resolve_scope(
        db,
        tenant_id=tenant_id,
        org_entity_id=org_entity_id,
        org_group_id=org_group_id,
        as_of_date=to_date,
        from_date=from_date,
        to_date=to_date,
    )

    cursor = _quarter_start(scope.from_date) if frequency == "quarterly" else _month_start(scope.from_date)
    revenue_points: list[TrendPoint] = []
    expense_points: list[TrendPoint] = []
    profit_points: list[TrendPoint] = []
    cash_points: list[TrendPoint] = []

    while cursor <= scope.to_date:
        period_from = cursor
        period_to = _month_end(cursor) if frequency == "monthly" else _month_end(date(cursor.year, cursor.month + 2 if cursor.month <= 10 else 12, 1))
        if period_to > scope.to_date:
            period_to = scope.to_date

        revenue = _ZERO
        expenses = _ZERO
        profit = _ZERO
        cash = _ZERO
        for entity_id in scope.entity_ids:
            pnl = await get_profit_and_loss(
                db,
                tenant_id=tenant_id,
                org_entity_id=entity_id,
                from_date=period_from,
                to_date=period_to,
            )
            cf = await get_cash_flow_statement(
                db,
                tenant_id=tenant_id,
                org_entity_id=entity_id,
                from_date=period_from,
                to_date=period_to,
            )
            revenue += pnl.revenue
            expenses += pnl.cost_of_sales + pnl.operating_expense + pnl.other_expense
            profit += pnl.net_profit
            cash += cf.net_cash_flow

        period_label = f"{period_from.year}-{str(period_from.month).zfill(2)}"
        revenue_points.append(TrendPoint(period=period_label, value=revenue))
        expense_points.append(TrendPoint(period=period_label, value=expenses))
        profit_points.append(TrendPoint(period=period_label, value=profit))
        cash_points.append(TrendPoint(period=period_label, value=cash))

        cursor = _next_period_start(cursor, frequency)

    series = [
        TrendSeries(metric_name="revenue", points=revenue_points),
        TrendSeries(metric_name="expenses", points=expense_points),
        TrendSeries(metric_name="profit", points=profit_points),
        TrendSeries(metric_name="cash", points=cash_points),
    ]

    snapshot = await create_snapshot(
        db,
        tenant_id=tenant_id,
        org_entity_id=scope.entity_ids[0] if len(scope.entity_ids) == 1 else None,
        org_group_id=uuid.UUID(scope.scope_dimension["org_group_id"])
        if "org_group_id" in scope.scope_dimension
        else None,
        snapshot_type="CF",
        as_of_date=scope.to_date,
        period_from=scope.from_date,
        period_to=scope.to_date,
        data_json={
            "frequency": frequency,
            "series": [item.model_dump(mode="json") for item in series],
            "dimension": scope.scope_dimension,
        },
    )
    await db.flush()

    return TrendResponse(
        frequency=frequency,
        series=series,
        snapshot={
            "snapshot_id": snapshot.id,
            "snapshot_type": snapshot.snapshot_type,
            "as_of_date": snapshot.as_of_date,
            "period_from": snapshot.period_from,
            "period_to": snapshot.period_to,
        },
    )

