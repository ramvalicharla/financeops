from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.analytics_layer import AnalyticsVariance
from financeops.modules.accounting_layer.application.financial_statements_service import get_profit_and_loss
from financeops.modules.analytics_layer.application.common import (
    create_snapshot,
    resolve_scope,
    variance_payload,
)
from financeops.modules.analytics_layer.application.kpi_service import calculate_kpi_metrics
from financeops.modules.analytics_layer.schemas import (
    AccountVarianceRow,
    VarianceMetricRow,
    VarianceResponse,
)

_ZERO = Decimal("0")


def _previous_window(from_date: date, to_date: date, comparison: str) -> tuple[date, date]:
    day_span = (to_date - from_date).days + 1
    if comparison == "prior_year":
        return date(from_date.year - 1, from_date.month, from_date.day), date(to_date.year - 1, to_date.month, to_date.day)
    prev_to = from_date - timedelta(days=1)
    prev_from = prev_to - timedelta(days=day_span - 1)
    return prev_from, prev_to


async def _pnl_account_map(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    entity_ids: list[uuid.UUID],
    from_date: date,
    to_date: date,
) -> dict[str, tuple[str, Decimal]]:
    rows: dict[str, tuple[str, Decimal]] = {}
    for entity_id in entity_ids:
        pnl = await get_profit_and_loss(
            db,
            tenant_id=tenant_id,
            org_entity_id=entity_id,
            from_date=from_date,
            to_date=to_date,
        )
        for item in pnl.breakdown:
            previous = rows.get(item.account_code)
            if previous is None:
                rows[item.account_code] = (item.account_name, item.amount)
            else:
                rows[item.account_code] = (previous[0], previous[1] + item.amount)
    return rows


async def compute_variance(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    org_entity_id: uuid.UUID | None,
    org_group_id: uuid.UUID | None,
    from_date: date,
    to_date: date,
    comparison: str = "prev_month",
) -> VarianceResponse:
    if comparison not in {"prev_month", "prior_year"}:
        raise ValueError("comparison must be prev_month or prior_year")

    current_scope = await resolve_scope(
        db,
        tenant_id=tenant_id,
        org_entity_id=org_entity_id,
        org_group_id=org_group_id,
        as_of_date=to_date,
        from_date=from_date,
        to_date=to_date,
    )
    previous_from, previous_to = _previous_window(from_date, to_date, comparison)
    previous_scope = await resolve_scope(
        db,
        tenant_id=tenant_id,
        org_entity_id=org_entity_id,
        org_group_id=org_group_id,
        as_of_date=previous_to,
        from_date=previous_from,
        to_date=previous_to,
    )

    current_metrics, _ = await calculate_kpi_metrics(db, tenant_id=tenant_id, scope=current_scope)
    previous_metrics, _ = await calculate_kpi_metrics(db, tenant_id=tenant_id, scope=previous_scope)

    metric_rows: list[VarianceMetricRow] = []
    dimension = {
        **current_scope.scope_dimension,
        "comparison": comparison,
        "current_from_date": str(from_date),
        "current_to_date": str(to_date),
        "previous_from_date": str(previous_from),
        "previous_to_date": str(previous_to),
    }
    for metric_name, current_value in current_metrics.items():
        previous_value = previous_metrics.get(metric_name, _ZERO)
        variance_value, variance_percent = variance_payload(current_value, previous_value)
        metric_rows.append(
            VarianceMetricRow(
                metric_name=metric_name,
                current_value=current_value,
                previous_value=previous_value,
                variance_value=variance_value,
                variance_percent=variance_percent,
            )
        )
        db.add(
            AnalyticsVariance(
                tenant_id=tenant_id,
                metric_name=metric_name,
                current_value=current_value,
                previous_value=previous_value,
                variance_value=variance_value,
                variance_percent=variance_percent,
                dimension_json=dimension,
            )
        )

    current_accounts = await _pnl_account_map(
        db,
        tenant_id=tenant_id,
        entity_ids=current_scope.entity_ids,
        from_date=from_date,
        to_date=to_date,
    )
    previous_accounts = await _pnl_account_map(
        db,
        tenant_id=tenant_id,
        entity_ids=previous_scope.entity_ids,
        from_date=previous_from,
        to_date=previous_to,
    )
    account_rows: list[AccountVarianceRow] = []
    for account_code in sorted(set(current_accounts) | set(previous_accounts)):
        current_name, current_value = current_accounts.get(account_code, ("UNKNOWN", _ZERO))
        _, previous_value = previous_accounts.get(account_code, (current_name, _ZERO))
        variance_value, variance_percent = variance_payload(current_value, previous_value)
        account_rows.append(
            AccountVarianceRow(
                account_code=account_code,
                account_name=current_name,
                current_value=current_value,
                previous_value=previous_value,
                variance_value=variance_value,
                variance_percent=variance_percent,
            )
        )

    snapshot = await create_snapshot(
        db,
        tenant_id=tenant_id,
        org_entity_id=current_scope.entity_ids[0] if len(current_scope.entity_ids) == 1 else None,
        org_group_id=uuid.UUID(current_scope.scope_dimension["org_group_id"])
        if "org_group_id" in current_scope.scope_dimension
        else None,
        snapshot_type="PNL",
        as_of_date=to_date,
        period_from=from_date,
        period_to=to_date,
        data_json={
            "comparison": comparison,
            "metric_variances": [row.model_dump(mode="json") for row in metric_rows],
            "account_variances": [row.model_dump(mode="json") for row in account_rows[:200]],
            "dimension": dimension,
        },
    )
    await db.flush()

    return VarianceResponse(
        comparison=comparison,
        current_period={"from_date": from_date, "to_date": to_date},
        previous_period={"from_date": previous_from, "to_date": previous_to},
        metric_variances=metric_rows,
        account_variances=account_rows,
        snapshot={
            "snapshot_id": snapshot.id,
            "snapshot_type": snapshot.snapshot_type,
            "as_of_date": snapshot.as_of_date,
            "period_from": snapshot.period_from,
            "period_to": snapshot.period_to,
        },
    )

