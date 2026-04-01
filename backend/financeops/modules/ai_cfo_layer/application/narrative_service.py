from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from financeops.modules.ai_cfo_layer.application.anomaly_service import detect_anomalies
from financeops.modules.ai_cfo_layer.application.recommendation_service import (
    generate_recommendations,
)
from financeops.modules.ai_cfo_layer.application.validation_service import (
    validate_generated_text_against_facts,
)
from financeops.modules.ai_cfo_layer.schemas import NarrativeResponse
from financeops.modules.analytics_layer.application.kpi_service import compute_kpis
from financeops.modules.analytics_layer.application.variance_service import compute_variance


def _metric_map(rows: list) -> dict[str, Decimal]:
    payload: dict[str, Decimal] = {}
    for row in rows:
        payload[row.metric_name] = Decimal(str(row.metric_value))
    return payload


async def generate_narrative(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    org_entity_id: uuid.UUID | None,
    org_group_id: uuid.UUID | None,
    from_date: date,
    to_date: date,
    comparison: str = "prev_month",
) -> NarrativeResponse:
    kpis = await compute_kpis(
        db,
        tenant_id=tenant_id,
        org_entity_id=org_entity_id,
        org_group_id=org_group_id,
        as_of_date=to_date,
        from_date=from_date,
        to_date=to_date,
    )
    variance = await compute_variance(
        db,
        tenant_id=tenant_id,
        org_entity_id=org_entity_id,
        org_group_id=org_group_id,
        from_date=from_date,
        to_date=to_date,
        comparison=comparison,
    )
    anomalies = await detect_anomalies(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        org_entity_id=org_entity_id,
        org_group_id=org_group_id,
        from_date=from_date,
        to_date=to_date,
        comparison=comparison,
        persist=False,
    )
    recommendations = await generate_recommendations(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        org_entity_id=org_entity_id,
        org_group_id=org_group_id,
        from_date=from_date,
        to_date=to_date,
        comparison=comparison,
        persist=False,
    )

    metrics = _metric_map(kpis.rows)
    revenue = metrics.get("revenue", Decimal("0"))
    net_profit = metrics.get("net_profit", Decimal("0"))
    net_margin = metrics.get("net_margin", Decimal("0"))
    operating_margin = metrics.get("operating_margin", Decimal("0"))

    revenue_variance = next(
        (item for item in variance.metric_variances if item.metric_name == "revenue"),
        None,
    )
    revenue_variance_pct = (
        Decimal(str(revenue_variance.variance_percent))
        if revenue_variance and revenue_variance.variance_percent is not None
        else Decimal("0")
    )

    summary = (
        f"Revenue closed at {revenue} with net profit {net_profit}; "
        f"net margin is {net_margin}% and operating margin is {operating_margin}%."
    )
    highlights = [
        (
            f"Revenue variance vs comparison period is {revenue_variance_pct}% "
            f"({revenue_variance.variance_value if revenue_variance else Decimal('0')})."
        ),
        f"Detected {len(anomalies.rows)} anomaly signals from deterministic KPI/trend checks.",
    ]
    drivers = []
    for row in variance.account_variances[:3]:
        drivers.append(
            f"{row.account_code} {row.account_name}: variance {row.variance_value} "
            f"({row.variance_percent if row.variance_percent is not None else Decimal('0')}%)."
        )
    risks = [
        f"{item.anomaly_type}: {item.explanation}"
        for item in anomalies.rows
        if item.severity in {"HIGH", "CRITICAL"}
    ][:3]
    actions = [item.message for item in recommendations.rows[:3]]

    allowed_numbers: list[Decimal] = [
        revenue,
        net_profit,
        net_margin,
        operating_margin,
        revenue_variance_pct,
        Decimal(str(len(anomalies.rows))),
    ]
    for line in highlights + drivers:
        for row in variance.metric_variances:
            allowed_numbers.extend(
                [
                    Decimal(str(row.current_value)),
                    Decimal(str(row.previous_value)),
                    Decimal(str(row.variance_value)),
                ]
            )
            if row.variance_percent is not None:
                allowed_numbers.append(Decimal(str(row.variance_percent)))
        validate_generated_text_against_facts(text=line, allowed_numbers=allowed_numbers)
    validate_generated_text_against_facts(text=summary, allowed_numbers=allowed_numbers)

    return NarrativeResponse(
        summary=summary,
        highlights=highlights,
        drivers=drivers,
        risks=risks,
        actions=actions,
        fact_basis={
            "kpis": {row.metric_name: str(row.metric_value) for row in kpis.rows},
            "comparison": comparison,
            "anomaly_count": len(anomalies.rows),
            "recommendation_count": len(recommendations.rows),
        },
        validation_passed=True,
    )

