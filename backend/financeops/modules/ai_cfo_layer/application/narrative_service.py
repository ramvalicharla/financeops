from __future__ import annotations

import json
import re
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import ValidationError
from financeops.db.models.ai_cfo_layer import AiCfoNarrativeBlock
from financeops.modules.ai_cfo_layer.domain.exceptions import AIResponseValidationError
from financeops.modules.ai_cfo_layer.infrastructure.ai_client import (
    AIClient,
    AIResponse,
    record_ai_cfo_ledger_entry,
)
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

_NUMBER_PATTERN = re.compile(r"-?\d+(?:\.\d+)?")


def _metric_map(rows: list) -> dict[str, Decimal]:
    payload: dict[str, Decimal] = {}
    for row in rows:
        payload[row.metric_name] = Decimal(str(row.metric_value))
    return payload


def _strip_code_fence(payload: str) -> str:
    text = payload.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 3:
            text = "\n".join(lines[1:-1]).strip()
    return text


def _build_allowed_numbers(
    metrics: dict[str, Decimal],
    variance,
    anomalies,
    recommendations,
) -> list[Decimal]:
    allowed_numbers: list[Decimal] = list(metrics.values())
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
    for row in variance.account_variances:
        allowed_numbers.extend(
            [
                Decimal(str(row.current_value)),
                Decimal(str(row.previous_value)),
                Decimal(str(row.variance_value)),
            ]
        )
        if row.variance_percent is not None:
            allowed_numbers.append(Decimal(str(row.variance_percent)))
    allowed_numbers.extend(
        [
            Decimal(str(len(anomalies.rows))),
            Decimal(str(len(recommendations.rows))),
        ]
    )
    for item in anomalies.rows:
        for token in _NUMBER_PATTERN.findall(str(item.explanation)):
            allowed_numbers.append(Decimal(token))
    for item in recommendations.rows:
        for token in _NUMBER_PATTERN.findall(str(item.message)):
            allowed_numbers.append(Decimal(token))
    return allowed_numbers


def _build_fact_basis(
    *,
    comparison: str,
    kpis,
    variance,
    anomalies,
    recommendations,
) -> dict[str, object]:
    return {
        "comparison": comparison,
        "kpis": {row.metric_name: str(row.metric_value) for row in kpis.rows},
        "metric_variances": [
            {
                "metric_name": row.metric_name,
                "current_value": str(row.current_value),
                "previous_value": str(row.previous_value),
                "variance_value": str(row.variance_value),
                "variance_percent": (
                    str(row.variance_percent) if row.variance_percent is not None else None
                ),
            }
            for row in variance.metric_variances
        ],
        "account_variances": [
            {
                "account_code": row.account_code,
                "account_name": row.account_name,
                "current_value": str(row.current_value),
                "previous_value": str(row.previous_value),
                "variance_value": str(row.variance_value),
                "variance_percent": (
                    str(row.variance_percent) if row.variance_percent is not None else None
                ),
            }
            for row in variance.account_variances[:5]
        ],
        "anomalies": [
            {
                "type": row.anomaly_type,
                "severity": row.severity,
                "explanation": row.explanation,
            }
            for row in anomalies.rows[:5]
        ],
        "recommendations": [row.message for row in recommendations.rows[:5]],
    }


def _build_deterministic_sections(
    *,
    metrics: dict[str, Decimal],
    variance,
    anomalies,
    recommendations,
) -> tuple[str, list[str], list[str], list[str], list[str]]:
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
    drivers = [
        (
            f"{row.account_code} {row.account_name}: variance {row.variance_value} "
            f"({row.variance_percent if row.variance_percent is not None else Decimal('0')}%)."
        )
        for row in variance.account_variances[:3]
    ]
    risks = [
        f"{item.anomaly_type}: {item.explanation}"
        for item in anomalies.rows
        if item.severity in {"HIGH", "CRITICAL"}
    ][:3]
    actions = [item.message for item in recommendations.rows[:3]]
    return summary, highlights, drivers, risks, actions


def _validate_sections(
    *,
    summary: str,
    highlights: list[str],
    drivers: list[str],
    risks: list[str],
    actions: list[str],
    allowed_numbers: list[Decimal],
) -> None:
    validate_generated_text_against_facts(text=summary, allowed_numbers=allowed_numbers)
    for line in highlights + drivers + risks + actions:
        validate_generated_text_against_facts(text=line, allowed_numbers=allowed_numbers)


def _build_ai_prompts(fact_basis: dict[str, object]) -> tuple[str, str]:
    system = (
        "You are Finqor AI CFO. Return strict JSON only with keys "
        "summary, highlights, drivers, risks, actions. "
        "Each of highlights, drivers, risks, and actions must be arrays of strings. "
        "Use only the facts and numeric strings provided. Do not invent numbers."
    )
    user = json.dumps(
        {
            "instruction": (
                "Write an executive finance narrative from the provided facts. "
                "Keep the summary concise and keep each array to at most three items."
            ),
            "facts": fact_basis,
        },
        sort_keys=True,
    )
    return system, user


def _parse_ai_response(payload: AIResponse) -> dict[str, object]:
    try:
        parsed = json.loads(_strip_code_fence(payload.text))
    except json.JSONDecodeError as exc:
        raise AIResponseValidationError(
            f"AI provider returned non-JSON narrative payload: {exc}"
        ) from exc
    required_keys = {"summary", "highlights", "drivers", "risks", "actions"}
    if not required_keys.issubset(parsed):
        raise AIResponseValidationError(
            "AI response missing required narrative keys."
        )
    return parsed


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
    ai_client: AIClient | None = None,
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
    allowed_numbers = _build_allowed_numbers(
        metrics=metrics,
        variance=variance,
        anomalies=anomalies,
        recommendations=recommendations,
    )
    fact_basis = _build_fact_basis(
        comparison=comparison,
        kpis=kpis,
        variance=variance,
        anomalies=anomalies,
        recommendations=recommendations,
    )

    if ai_client is None:
        summary, highlights, drivers, risks, actions = _build_deterministic_sections(
            metrics=metrics,
            variance=variance,
            anomalies=anomalies,
            recommendations=recommendations,
        )
        _validate_sections(
            summary=summary,
            highlights=highlights,
            drivers=drivers,
            risks=risks,
            actions=actions,
            allowed_numbers=allowed_numbers,
        )
        return NarrativeResponse(
            summary=summary,
            highlights=highlights,
            drivers=drivers,
            risks=risks,
            actions=actions,
            fact_basis={
                **fact_basis,
                "anomaly_count": len(anomalies.rows),
                "recommendation_count": len(recommendations.rows),
            },
            validation_passed=True,
        )

    system_prompt, user_prompt = _build_ai_prompts(fact_basis)
    ai_response = await ai_client.complete(system_prompt, user_prompt, max_tokens=1000)
    parsed = _parse_ai_response(ai_response)
    summary = str(parsed["summary"])
    highlights = [str(item) for item in list(parsed["highlights"])[:3]]
    drivers = [str(item) for item in list(parsed["drivers"])[:3]]
    risks = [str(item) for item in list(parsed["risks"])[:3]]
    actions = [str(item) for item in list(parsed["actions"])[:3]]
    try:
        _validate_sections(
            summary=summary,
            highlights=highlights,
            drivers=drivers,
            risks=risks,
            actions=actions,
            allowed_numbers=allowed_numbers,
        )
    except ValidationError as exc:
        raise AIResponseValidationError(str(exc)) from exc
    await record_ai_cfo_ledger_entry(
        db,
        tenant_id=tenant_id,
        feature="narrative",
        response=ai_response,
    )
    db.add(
        AiCfoNarrativeBlock(
            tenant_id=tenant_id,
            created_by=actor_user_id,
            provider=ai_response.provider_used,
            llm_model=ai_response.model_used,
            summary=summary,
            highlights_json=highlights,
            drivers_json=drivers,
            risks_json=risks,
            actions_json=actions,
            fact_basis_json={
                **fact_basis,
                "provider_used": ai_response.provider_used,
                "model_used": ai_response.model_used,
                "prompt_tokens": ai_response.prompt_tokens,
                "completion_tokens": ai_response.completion_tokens,
            },
        )
    )

    return NarrativeResponse(
        summary=summary,
        highlights=highlights,
        drivers=drivers,
        risks=risks,
        actions=actions,
        fact_basis={
            **fact_basis,
            "provider_used": ai_response.provider_used,
            "model_used": ai_response.model_used,
        },
        validation_passed=True,
        generation_method="llm",
    )
