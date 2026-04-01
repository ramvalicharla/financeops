from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from statistics import mean

from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.ai_cfo_layer import AiCfoAnomaly
from financeops.modules.ai_cfo_layer.schemas import AnomalyResponse, AnomalyRow
from financeops.modules.analytics_layer.application.trend_service import compute_trends
from financeops.modules.analytics_layer.application.variance_service import compute_variance

_ZERO = Decimal("0")


def _severity_from_percent(value: Decimal) -> str:
    pct = abs(value)
    if pct >= Decimal("50"):
        return "CRITICAL"
    if pct >= Decimal("30"):
        return "HIGH"
    if pct >= Decimal("20"):
        return "MEDIUM"
    return "LOW"


def _to_decimal(value: Decimal | None) -> Decimal:
    if value is None:
        return _ZERO
    return Decimal(str(value))


async def detect_anomalies(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    org_entity_id: uuid.UUID | None,
    org_group_id: uuid.UUID | None,
    from_date: date,
    to_date: date,
    comparison: str = "prev_month",
    persist: bool = True,
) -> AnomalyResponse:
    variance = await compute_variance(
        db,
        tenant_id=tenant_id,
        org_entity_id=org_entity_id,
        org_group_id=org_group_id,
        from_date=from_date,
        to_date=to_date,
        comparison=comparison,
    )
    trends = await compute_trends(
        db,
        tenant_id=tenant_id,
        org_entity_id=org_entity_id,
        org_group_id=org_group_id,
        from_date=from_date,
        to_date=to_date,
        frequency="monthly",
    )

    results: list[AnomalyRow] = []
    metric_map = {item.metric_name: item for item in variance.metric_variances}

    def append_metric_anomaly(metric_name: str, anomaly_type: str, message: str) -> None:
        row = metric_map.get(metric_name)
        if row is None:
            return
        pct = _to_decimal(row.variance_percent)
        if abs(pct) < Decimal("20"):
            return
        results.append(
            AnomalyRow(
                metric_name=metric_name,
                anomaly_type=anomaly_type,
                deviation_value=_to_decimal(row.variance_value),
                severity=_severity_from_percent(pct),  # type: ignore[arg-type]
                explanation=message.format(
                    current=row.current_value,
                    previous=row.previous_value,
                    variance=row.variance_value,
                    variance_percent=pct,
                ),
                facts={
                    "current_value": str(row.current_value),
                    "previous_value": str(row.previous_value),
                    "variance_value": str(row.variance_value),
                    "variance_percent": str(pct),
                },
                lineage={
                    "source": "analytics.variance",
                    "comparison": comparison,
                    "period": {
                        "from_date": str(from_date),
                        "to_date": str(to_date),
                    },
                },
            )
        )

    revenue_pct = _to_decimal(metric_map.get("revenue").variance_percent if metric_map.get("revenue") else None)
    if revenue_pct >= Decimal("20"):
        append_metric_anomaly(
            "revenue",
            "REVENUE_SPIKE",
            "Revenue increased by {variance_percent}% (current {current}, previous {previous}).",
        )
    elif revenue_pct <= Decimal("-20"):
        append_metric_anomaly(
            "revenue",
            "REVENUE_DROP",
            "Revenue declined by {variance_percent}% (current {current}, previous {previous}).",
        )

    append_metric_anomaly(
        "operating_margin",
        "MARGIN_DEVIATION",
        "Operating margin shifted by {variance_percent}% (current {current}, previous {previous}).",
    )
    append_metric_anomaly(
        "net_margin",
        "NET_MARGIN_DEVIATION",
        "Net margin shifted by {variance_percent}% (current {current}, previous {previous}).",
    )

    for account_row in variance.account_variances:
        text = f"{account_row.account_code} {account_row.account_name}".upper()
        pct = _to_decimal(account_row.variance_percent)
        if abs(pct) < Decimal("25"):
            continue
        if "EXPENSE" in text or "COST" in text:
            results.append(
                AnomalyRow(
                    metric_name=account_row.account_code,
                    anomaly_type="EXPENSE_OUTLIER",
                    deviation_value=account_row.variance_value,
                    severity=_severity_from_percent(pct),  # type: ignore[arg-type]
                    explanation=(
                        f"Expense outlier detected for {account_row.account_code} "
                        f"({account_row.account_name}) with {pct}% variance."
                    ),
                    facts={
                        "account_code": account_row.account_code,
                        "account_name": account_row.account_name,
                        "current_value": str(account_row.current_value),
                        "previous_value": str(account_row.previous_value),
                        "variance_value": str(account_row.variance_value),
                        "variance_percent": str(pct),
                    },
                    lineage={
                        "source": "analytics.variance.account",
                        "comparison": comparison,
                    },
                )
            )

    cash_series = next(
        (series for series in trends.series if series.metric_name == "cash"),
        None,
    )
    if cash_series and len(cash_series.points) >= 3:
        values = [Decimal(str(point.value)) for point in cash_series.points]
        latest = values[-1]
        historical = values[:-1]
        historical_mean = Decimal(str(mean(historical))) if historical else _ZERO
        if historical_mean != _ZERO:
            deviation_pct = ((latest - historical_mean) / historical_mean * Decimal("100")).quantize(
                Decimal("0.000001")
            )
            if abs(deviation_pct) >= Decimal("30"):
                results.append(
                    AnomalyRow(
                        metric_name="cash",
                        anomaly_type="CASH_ANOMALY",
                        deviation_value=(latest - historical_mean).quantize(Decimal("0.000001")),
                        severity=_severity_from_percent(deviation_pct),  # type: ignore[arg-type]
                        explanation=(
                            f"Cash movement anomaly detected: latest {latest} vs historical mean "
                            f"{historical_mean} ({deviation_pct}%)."
                        ),
                        facts={
                            "latest_cash": str(latest),
                            "historical_mean": str(historical_mean),
                            "deviation_percent": str(deviation_pct),
                            "points": [str(item) for item in values],
                        },
                        lineage={
                            "source": "analytics.trends.cash",
                            "frequency": trends.frequency,
                        },
                    )
                )

    if persist:
        for anomaly in results:
            row = AiCfoAnomaly(
                tenant_id=tenant_id,
                org_entity_id=org_entity_id,
                org_group_id=org_group_id,
                metric_name=anomaly.metric_name,
                anomaly_type=anomaly.anomaly_type,
                deviation_value=anomaly.deviation_value,
                severity=anomaly.severity,
                fact_json=anomaly.facts,
                lineage_json=anomaly.lineage,
                created_by=actor_user_id,
            )
            db.add(row)
            await db.flush()
            anomaly.id = row.id
            anomaly.created_at = row.created_at

    return AnomalyResponse(
        rows=results,
        validation={
            "deterministic_sources": [
                "analytics.variance",
                "analytics.trends",
            ],
            "hallucination_check": "rule_based_only",
            "count": len(results),
        },
    )

