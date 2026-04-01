from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from financeops.modules.analytics_layer.application.common import (
    compute_statement_bundle,
    create_metric_rows,
    create_snapshot,
    resolve_scope,
)
from financeops.modules.analytics_layer.schemas import AnalyticsMetricRow, RatioResponse

_ZERO = Decimal("0")


def _safe_div(numerator: Decimal, denominator: Decimal) -> Decimal:
    if denominator == _ZERO:
        return _ZERO
    return (numerator / denominator).quantize(Decimal("0.000001"))


def _safe_pct(numerator: Decimal, denominator: Decimal) -> Decimal:
    return (_safe_div(numerator, denominator) * Decimal("100")).quantize(Decimal("0.000001"))


def _account_total(items: list[Any], *keywords: str) -> Decimal:
    total = _ZERO
    tokens = tuple(word.upper() for word in keywords)
    for item in items:
        text = f"{item.account_code} {item.account_name}".upper()
        if any(token in text for token in tokens):
            total += item.amount
    return total


def _metric(name: str, value: Decimal, dimension: dict[str, Any]) -> AnalyticsMetricRow:
    return AnalyticsMetricRow(metric_name=name, metric_value=value, dimension=dimension)


async def compute_ratios(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    org_entity_id: uuid.UUID | None,
    org_group_id: uuid.UUID | None,
    as_of_date: date | None,
    from_date: date | None,
    to_date: date | None,
) -> RatioResponse:
    scope = await resolve_scope(
        db,
        tenant_id=tenant_id,
        org_entity_id=org_entity_id,
        org_group_id=org_group_id,
        as_of_date=as_of_date,
        from_date=from_date,
        to_date=to_date,
    )

    revenue = _ZERO
    cogs = _ZERO
    net_profit = _ZERO
    assets_total = _ZERO
    equity_total = _ZERO
    opening_assets_total = _ZERO
    opening_equity_total = _ZERO
    inventory_closing = _ZERO
    inventory_opening = _ZERO
    receivables_closing = _ZERO
    payables_closing = _ZERO

    opening_date = scope.from_date - timedelta(days=1)
    for entity_id in scope.entity_ids:
        current = await compute_statement_bundle(
            db,
            tenant_id=tenant_id,
            entity_id=entity_id,
            from_date=scope.from_date,
            to_date=scope.to_date,
            as_of_date=scope.as_of_date,
        )
        opening = await compute_statement_bundle(
            db,
            tenant_id=tenant_id,
            entity_id=entity_id,
            from_date=scope.from_date,
            to_date=scope.to_date,
            as_of_date=opening_date,
        )

        pnl = current["pnl"]
        bs = current["bs"]
        obs = opening["bs"]

        revenue += pnl.revenue
        net_profit += pnl.net_profit
        cogs += pnl.cost_of_sales
        assets_total += bs.totals.assets
        equity_total += bs.totals.equity
        opening_assets_total += obs.totals.assets
        opening_equity_total += obs.totals.equity

        inventory_closing += _account_total(bs.assets, "INVENT")
        inventory_opening += _account_total(obs.assets, "INVENT")
        receivables_closing += _account_total(bs.assets, "RECEIV")
        payables_closing += _account_total(bs.liabilities, "PAYABLE")

    avg_assets = ((assets_total + opening_assets_total) / Decimal("2")).quantize(Decimal("0.000001"))
    avg_equity = ((equity_total + opening_equity_total) / Decimal("2")).quantize(Decimal("0.000001"))
    avg_inventory = ((inventory_closing + inventory_opening) / Decimal("2")).quantize(Decimal("0.000001"))
    day_count = Decimal(str((scope.to_date - scope.from_date).days + 1))

    metrics = {
        "roe": _safe_pct(net_profit, avg_equity),
        "roa": _safe_pct(net_profit, avg_assets),
        "asset_turnover": _safe_div(revenue, avg_assets),
        "inventory_turnover": _safe_div(cogs, avg_inventory) if avg_inventory != _ZERO else _ZERO,
        "receivable_days": (_safe_div(receivables_closing, revenue) * day_count).quantize(Decimal("0.000001"))
        if revenue != _ZERO
        else _ZERO,
        "payable_days": (_safe_div(payables_closing, cogs) * day_count).quantize(Decimal("0.000001"))
        if cogs != _ZERO
        else _ZERO,
    }

    dimension = {
        **scope.scope_dimension,
        "from_date": str(scope.from_date),
        "to_date": str(scope.to_date),
        "as_of_date": str(scope.as_of_date),
    }

    snapshot = await create_snapshot(
        db,
        tenant_id=tenant_id,
        org_entity_id=scope.entity_ids[0] if len(scope.entity_ids) == 1 else None,
        org_group_id=uuid.UUID(scope.scope_dimension["org_group_id"]) if "org_group_id" in scope.scope_dimension else None,
        snapshot_type="BS",
        as_of_date=scope.as_of_date,
        period_from=scope.from_date,
        period_to=scope.to_date,
        data_json={
            "metrics": {k: str(v) for k, v in metrics.items()},
            "basis": {
                "avg_assets": str(avg_assets),
                "avg_equity": str(avg_equity),
                "avg_inventory": str(avg_inventory),
                "revenue": str(revenue),
                "cogs": str(cogs),
                "net_profit": str(net_profit),
            },
            "dimension": dimension,
        },
    )
    await create_metric_rows(
        db,
        tenant_id=tenant_id,
        metrics=metrics,
        dimension_json=dimension,
    )

    rows = [_metric(name, value, dimension) for name, value in metrics.items()]
    return RatioResponse(
        rows=rows,
        snapshot={
            "snapshot_id": snapshot.id,
            "snapshot_type": snapshot.snapshot_type,
            "as_of_date": snapshot.as_of_date,
            "period_from": snapshot.period_from,
            "period_to": snapshot.period_to,
        },
        lineage={
            "formula_basis": {
                "avg_assets": str(avg_assets),
                "avg_equity": str(avg_equity),
                "avg_inventory": str(avg_inventory),
            }
        },
    )

