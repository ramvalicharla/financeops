from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from financeops.modules.analytics_layer.application.common import (
    ResolvedScope,
    compute_statement_bundle,
    create_metric_rows,
    create_snapshot,
    resolve_scope,
)
from financeops.modules.analytics_layer.schemas import AnalyticsMetricRow, KpiResponse

_ZERO = Decimal("0")


def _safe_div(numerator: Decimal, denominator: Decimal) -> Decimal:
    if denominator == _ZERO:
        return _ZERO
    return (numerator / denominator).quantize(Decimal("0.000001"))


def _safe_pct(numerator: Decimal, denominator: Decimal) -> Decimal:
    return (_safe_div(numerator, denominator) * Decimal("100")).quantize(Decimal("0.000001"))


def _metric(name: str, value: Decimal, dimension: dict[str, Any]) -> AnalyticsMetricRow:
    return AnalyticsMetricRow(metric_name=name, metric_value=value, dimension=dimension)


def _sum_current_assets(bs_payload: Any) -> Decimal:
    return sum((item.amount for item in bs_payload.assets if (item.sub_type or "").upper() == "CURRENT"), _ZERO)


def _sum_current_liabilities(bs_payload: Any) -> Decimal:
    return sum(
        (item.amount for item in bs_payload.liabilities if (item.sub_type or "").upper() == "CURRENT"),
        _ZERO,
    )


def _sum_inventory(bs_payload: Any) -> Decimal:
    total = _ZERO
    for item in bs_payload.assets:
        text = f"{item.account_code} {item.account_name}".upper()
        if "INVENT" in text:
            total += item.amount
    return total


def _extract_interest_expense(pnl_payload: Any) -> Decimal:
    total = _ZERO
    for row in pnl_payload.breakdown:
        text = f"{row.account_code} {row.account_name}".upper()
        if "INTEREST" in text or "FINANCE" in text:
            total += row.amount
    return total


def _extract_depr_amort(pnl_payload: Any) -> Decimal:
    total = _ZERO
    for row in pnl_payload.breakdown:
        text = f"{row.account_code} {row.account_name}".upper()
        if "DEPRECI" in text or "AMORT" in text:
            total += row.amount
    return total


async def compute_kpis(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    org_entity_id: uuid.UUID | None,
    org_group_id: uuid.UUID | None,
    as_of_date: date | None,
    from_date: date | None,
    to_date: date | None,
) -> KpiResponse:
    scope = await resolve_scope(
        db,
        tenant_id=tenant_id,
        org_entity_id=org_entity_id,
        org_group_id=org_group_id,
        as_of_date=as_of_date,
        from_date=from_date,
        to_date=to_date,
    )
    return await _compute_kpis_for_scope(db, tenant_id=tenant_id, scope=scope)


async def _compute_kpis_for_scope(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    scope: ResolvedScope,
) -> KpiResponse:
    metrics, lineage_entities = await calculate_kpi_metrics(
        db,
        tenant_id=tenant_id,
        scope=scope,
    )
    dimension = {
        **scope.scope_dimension,
        "from_date": str(scope.from_date),
        "to_date": str(scope.to_date),
        "as_of_date": str(scope.as_of_date),
    }
    metric_rows = [_metric(name, value, dimension) for name, value in metrics.items()]

    snapshot = await create_snapshot(
        db,
        tenant_id=tenant_id,
        org_entity_id=scope.entity_ids[0] if len(scope.entity_ids) == 1 else None,
        org_group_id=uuid.UUID(scope.scope_dimension["org_group_id"]) if "org_group_id" in scope.scope_dimension else None,
        snapshot_type="PNL",
        as_of_date=scope.as_of_date,
        period_from=scope.from_date,
        period_to=scope.to_date,
        data_json={
            "metrics": {k: str(v) for k, v in metrics.items()},
            "lineage": {
                "source": "financial_statements_service",
                "entities": lineage_entities,
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

    return KpiResponse(
        rows=metric_rows,
        snapshot={
            "snapshot_id": snapshot.id,
            "snapshot_type": snapshot.snapshot_type,
            "as_of_date": snapshot.as_of_date,
            "period_from": snapshot.period_from,
            "period_to": snapshot.period_to,
        },
        lineage={"entities": lineage_entities},
    )


async def calculate_kpi_metrics(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    scope: ResolvedScope,
) -> tuple[dict[str, Decimal], list[dict[str, Any]]]:
    revenue = _ZERO
    gross_profit = _ZERO
    operating_profit = _ZERO
    net_profit = _ZERO
    current_assets = _ZERO
    current_liabilities = _ZERO
    inventory = _ZERO
    liabilities_total = _ZERO
    equity_total = _ZERO
    interest_expense = _ZERO
    depreciation_amort = _ZERO

    lineage_entities: list[dict[str, Any]] = []
    for entity_id in scope.entity_ids:
        bundle = await compute_statement_bundle(
            db,
            tenant_id=tenant_id,
            entity_id=entity_id,
            from_date=scope.from_date,
            to_date=scope.to_date,
            as_of_date=scope.as_of_date,
        )
        pnl = bundle["pnl"]
        bs = bundle["bs"]
        cf = bundle["cf"]

        revenue += pnl.revenue
        gross_profit += pnl.gross_profit
        operating_profit += pnl.operating_profit
        net_profit += pnl.net_profit
        current_assets += _sum_current_assets(bs)
        current_liabilities += _sum_current_liabilities(bs)
        inventory += _sum_inventory(bs)
        liabilities_total += bs.totals.liabilities
        equity_total += bs.totals.equity
        interest_expense += _extract_interest_expense(pnl)
        depreciation_amort += _extract_depr_amort(pnl)

        lineage_entities.append(
            {
                "org_entity_id": str(entity_id),
                "pnl_from_date": str(pnl.from_date),
                "pnl_to_date": str(pnl.to_date),
                "bs_as_of_date": str(bs.as_of_date),
                "cash_flow_net_cash_flow": str(cf.net_cash_flow),
            }
        )

    ebitda = operating_profit + depreciation_amort
    operating_margin = _safe_pct(operating_profit, revenue)
    net_margin = _safe_pct(net_profit, revenue)
    current_ratio = _safe_div(current_assets, current_liabilities)
    quick_ratio = _safe_div(current_assets - inventory, current_liabilities)
    debt_to_equity = _safe_div(liabilities_total, equity_total)
    interest_coverage = _safe_div(operating_profit, interest_expense)

    metrics = {
        "revenue": revenue,
        "gross_profit": gross_profit,
        "ebitda": ebitda,
        "net_profit": net_profit,
        "operating_margin": operating_margin,
        "net_margin": net_margin,
        "current_ratio": current_ratio,
        "quick_ratio": quick_ratio,
        "debt_equity": debt_to_equity,
        "interest_coverage": interest_coverage,
    }
    return metrics, lineage_entities
