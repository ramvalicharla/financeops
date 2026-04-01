from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.ai_cfo_layer import AiCfoRecommendation
from financeops.modules.ai_cfo_layer.application.validation_service import (
    validate_generated_text_against_facts,
)
from financeops.modules.ai_cfo_layer.schemas import RecommendationRow, RecommendationsResponse
from financeops.modules.analytics_layer.application.kpi_service import compute_kpis
from financeops.modules.analytics_layer.application.ratio_service import compute_ratios
from financeops.modules.analytics_layer.application.variance_service import compute_variance

_ZERO = Decimal("0")


def _severity_from_score(score: Decimal) -> str:
    if score >= Decimal("90"):
        return "CRITICAL"
    if score >= Decimal("70"):
        return "HIGH"
    if score >= Decimal("40"):
        return "MEDIUM"
    return "LOW"


def _metric_map(rows: list[RecommendationRow]) -> dict[str, RecommendationRow]:
    return {f"{row.recommendation_type}:{index}": row for index, row in enumerate(rows)}


def _to_map(response_rows: list) -> dict[str, Decimal]:
    payload: dict[str, Decimal] = {}
    for item in response_rows:
        payload[item.metric_name] = Decimal(str(item.metric_value))
    return payload


async def generate_recommendations(
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
) -> RecommendationsResponse:
    kpis = await compute_kpis(
        db,
        tenant_id=tenant_id,
        org_entity_id=org_entity_id,
        org_group_id=org_group_id,
        as_of_date=to_date,
        from_date=from_date,
        to_date=to_date,
    )
    ratios = await compute_ratios(
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

    kpi_map = _to_map(kpis.rows)
    ratio_map = _to_map(ratios.rows)
    variance_map = {item.metric_name: item for item in variance.metric_variances}

    recommendations: list[RecommendationRow] = []

    receivable_days = ratio_map.get("receivable_days", _ZERO)
    if receivable_days > Decimal("45"):
        msg = (
            f"Receivable days at {receivable_days} exceeds 45; prioritize collections, "
            "review overdue buckets, and tighten customer credit controls."
        )
        validate_generated_text_against_facts(text=msg, allowed_numbers=[receivable_days, Decimal("45")])
        recommendations.append(
            RecommendationRow(
                recommendation_type="WORKING_CAPITAL_COLLECTION",
                severity="HIGH",
                message=msg,
                evidence={"receivable_days": str(receivable_days), "threshold": "45"},
            )
        )

    net_margin = kpi_map.get("net_margin", _ZERO)
    if net_margin < Decimal("10"):
        msg = (
            f"Net margin at {net_margin}% is below 10%; investigate high-variance expense lines "
            "and review pricing/cost mix by entity."
        )
        validate_generated_text_against_facts(text=msg, allowed_numbers=[net_margin, Decimal("10")])
        recommendations.append(
            RecommendationRow(
                recommendation_type="MARGIN_RECOVERY",
                severity="MEDIUM",
                message=msg,
                evidence={"net_margin": str(net_margin), "threshold": "10"},
            )
        )

    current_ratio = kpi_map.get("current_ratio", _ZERO)
    if current_ratio < Decimal("1"):
        msg = (
            f"Current ratio at {current_ratio} is below 1.0; trigger liquidity actions, "
            "defer discretionary spend, and accelerate receivables."
        )
        validate_generated_text_against_facts(text=msg, allowed_numbers=[current_ratio, Decimal("1")])
        recommendations.append(
            RecommendationRow(
                recommendation_type="LIQUIDITY_WARNING",
                severity="HIGH",
                message=msg,
                evidence={"current_ratio": str(current_ratio), "threshold": "1"},
            )
        )

    debt_equity = kpi_map.get("debt_equity", _ZERO)
    if debt_equity > Decimal("2"):
        msg = (
            f"Debt-to-equity at {debt_equity} exceeds 2.0; evaluate refinancing plan and "
            "deleveraging options before next close."
        )
        validate_generated_text_against_facts(text=msg, allowed_numbers=[debt_equity, Decimal("2")])
        recommendations.append(
            RecommendationRow(
                recommendation_type="LEVERAGE_RISK",
                severity="MEDIUM",
                message=msg,
                evidence={"debt_equity": str(debt_equity), "threshold": "2"},
            )
        )

    revenue_variance = variance_map.get("revenue")
    if revenue_variance and revenue_variance.variance_percent is not None:
        revenue_var_pct = Decimal(str(revenue_variance.variance_percent))
        if revenue_var_pct <= Decimal("-20"):
            msg = (
                f"Revenue variance at {revenue_var_pct}% indicates a sharp contraction; "
                "run entity-wise pipeline review and revise cash plan."
            )
            validate_generated_text_against_facts(
                text=msg,
                allowed_numbers=[revenue_var_pct, Decimal("-20")],
            )
            recommendations.append(
                RecommendationRow(
                    recommendation_type="REVENUE_DECLINE_RESPONSE",
                    severity="HIGH",
                    message=msg,
                    evidence={"revenue_variance_percent": str(revenue_var_pct)},
                )
            )

    if kpi_map.get("net_profit", _ZERO) < _ZERO:
        net_profit = kpi_map["net_profit"]
        msg = (
            f"Net profit is negative ({net_profit}); freeze non-essential costs and "
            "prioritize profitability remediation in the next operating cycle."
        )
        validate_generated_text_against_facts(text=msg, allowed_numbers=[net_profit])
        recommendations.append(
            RecommendationRow(
                recommendation_type="LOSS_CONTAINMENT",
                severity="CRITICAL",
                message=msg,
                evidence={"net_profit": str(net_profit)},
            )
        )

    for row in recommendations:
        score = Decimal("30")
        if row.severity == "MEDIUM":
            score = Decimal("50")
        elif row.severity == "HIGH":
            score = Decimal("80")
        elif row.severity == "CRITICAL":
            score = Decimal("95")
        row.evidence["severity_score"] = str(score)
        row.evidence["normalized_severity"] = _severity_from_score(score)

    if persist:
        for row in recommendations:
            saved = AiCfoRecommendation(
                tenant_id=tenant_id,
                org_entity_id=org_entity_id,
                org_group_id=org_group_id,
                recommendation_type=row.recommendation_type,
                message=row.message,
                severity=row.severity,
                evidence_json=row.evidence,
                created_by=actor_user_id,
            )
            db.add(saved)
            await db.flush()
            row.id = saved.id
            row.created_at = saved.created_at

    return RecommendationsResponse(
        rows=recommendations,
        validation={
            "deterministic_sources": [
                "analytics.kpis",
                "analytics.ratios",
                "analytics.variance",
            ],
            "row_count": len(recommendations),
            "lineage_map": list(_metric_map(recommendations).keys()),
        },
    )

