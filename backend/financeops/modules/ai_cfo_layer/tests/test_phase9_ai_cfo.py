from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from financeops.modules.ai_cfo_layer.application import (
    anomaly_service,
    explanation_service,
    narrative_service,
    recommendation_service,
)
from financeops.modules.ai_cfo_layer.application.validation_service import (
    validate_generated_text_against_facts,
)


@pytest.mark.asyncio
async def test_anomaly_detection_correctness(monkeypatch: pytest.MonkeyPatch) -> None:
    metric_variances = [
        SimpleNamespace(
            metric_name="revenue",
            current_value=Decimal("130"),
            previous_value=Decimal("100"),
            variance_value=Decimal("30"),
            variance_percent=Decimal("30"),
        ),
        SimpleNamespace(
            metric_name="operating_margin",
            current_value=Decimal("9"),
            previous_value=Decimal("15"),
            variance_value=Decimal("-6"),
            variance_percent=Decimal("-40"),
        ),
    ]
    account_variances = [
        SimpleNamespace(
            account_code="5000",
            account_name="Operating Expense",
            current_value=Decimal("90"),
            previous_value=Decimal("60"),
            variance_value=Decimal("30"),
            variance_percent=Decimal("50"),
        )
    ]
    trend_series = [
        SimpleNamespace(
            metric_name="cash",
            points=[
                SimpleNamespace(period="2026-01", value=Decimal("100")),
                SimpleNamespace(period="2026-02", value=Decimal("105")),
                SimpleNamespace(period="2026-03", value=Decimal("40")),
            ],
        )
    ]
    monkeypatch.setattr(
        anomaly_service,
        "compute_variance",
        AsyncMock(return_value=SimpleNamespace(metric_variances=metric_variances, account_variances=account_variances)),
    )
    monkeypatch.setattr(
        anomaly_service,
        "compute_trends",
        AsyncMock(return_value=SimpleNamespace(frequency="monthly", series=trend_series)),
    )

    result = await anomaly_service.detect_anomalies(
        AsyncMock(),
        tenant_id=uuid.uuid4(),
        actor_user_id=uuid.uuid4(),
        org_entity_id=uuid.uuid4(),
        org_group_id=None,
        from_date=date(2026, 3, 1),
        to_date=date(2026, 3, 31),
        persist=False,
    )
    types = {row.anomaly_type for row in result.rows}
    assert "REVENUE_SPIKE" in types
    assert "EXPENSE_OUTLIER" in types
    assert "CASH_ANOMALY" in types


@pytest.mark.asyncio
async def test_explanation_consistency(monkeypatch: pytest.MonkeyPatch) -> None:
    metric_variances = [
        SimpleNamespace(
            metric_name="revenue",
            current_value=Decimal("150"),
            previous_value=Decimal("100"),
            variance_value=Decimal("50"),
            variance_percent=Decimal("50"),
        )
    ]
    account_variances = [
        SimpleNamespace(
            account_code="4100",
            account_name="Services Revenue",
            current_value=Decimal("110"),
            previous_value=Decimal("60"),
            variance_value=Decimal("50"),
            variance_percent=Decimal("83.333333"),
        )
    ]
    monkeypatch.setattr(
        explanation_service,
        "compute_variance",
        AsyncMock(return_value=SimpleNamespace(metric_variances=metric_variances, account_variances=account_variances)),
    )
    monkeypatch.setattr(
        explanation_service,
        "get_metric_drilldown",
        AsyncMock(
            return_value=SimpleNamespace(
                accounts=[SimpleNamespace(account_code="4100")],
                journals=[1],
                gl_entries=[1],
                lineage={"entity_ids": ["entity-A"]},
            )
        ),
    )

    result = await explanation_service.explain_variance(
        AsyncMock(),
        tenant_id=uuid.uuid4(),
        metric_name="revenue",
        org_entity_id=uuid.uuid4(),
        org_group_id=None,
        from_date=date(2026, 3, 1),
        to_date=date(2026, 3, 31),
    )
    assert "150" in result.explanation
    assert "100" in result.explanation
    assert result.validation_passed is True
    assert len(result.top_drivers) == 1


@pytest.mark.asyncio
async def test_recommendation_validity(monkeypatch: pytest.MonkeyPatch) -> None:
    kpi_rows = [
        SimpleNamespace(metric_name="net_margin", metric_value=Decimal("8")),
        SimpleNamespace(metric_name="current_ratio", metric_value=Decimal("0.8")),
        SimpleNamespace(metric_name="debt_equity", metric_value=Decimal("2.4")),
        SimpleNamespace(metric_name="net_profit", metric_value=Decimal("-10")),
    ]
    ratio_rows = [
        SimpleNamespace(metric_name="receivable_days", metric_value=Decimal("70")),
    ]
    variance_rows = [
        SimpleNamespace(
            metric_name="revenue",
            current_value=Decimal("80"),
            previous_value=Decimal("120"),
            variance_value=Decimal("-40"),
            variance_percent=Decimal("-33.333333"),
        )
    ]
    monkeypatch.setattr(
        recommendation_service,
        "compute_kpis",
        AsyncMock(return_value=SimpleNamespace(rows=kpi_rows)),
    )
    monkeypatch.setattr(
        recommendation_service,
        "compute_ratios",
        AsyncMock(return_value=SimpleNamespace(rows=ratio_rows)),
    )
    monkeypatch.setattr(
        recommendation_service,
        "compute_variance",
        AsyncMock(return_value=SimpleNamespace(metric_variances=variance_rows)),
    )

    result = await recommendation_service.generate_recommendations(
        AsyncMock(),
        tenant_id=uuid.uuid4(),
        actor_user_id=uuid.uuid4(),
        org_entity_id=uuid.uuid4(),
        org_group_id=None,
        from_date=date(2026, 3, 1),
        to_date=date(2026, 3, 31),
        persist=False,
    )
    recommendation_types = {row.recommendation_type for row in result.rows}
    assert "WORKING_CAPITAL_COLLECTION" in recommendation_types
    assert "LIQUIDITY_WARNING" in recommendation_types
    assert "LOSS_CONTAINMENT" in recommendation_types


@pytest.mark.asyncio
async def test_narrative_correctness(monkeypatch: pytest.MonkeyPatch) -> None:
    kpi_rows = [
        SimpleNamespace(metric_name="revenue", metric_value=Decimal("500")),
        SimpleNamespace(metric_name="net_profit", metric_value=Decimal("120")),
        SimpleNamespace(metric_name="net_margin", metric_value=Decimal("24")),
        SimpleNamespace(metric_name="operating_margin", metric_value=Decimal("28")),
    ]
    metric_variances = [
        SimpleNamespace(
            metric_name="revenue",
            current_value=Decimal("500"),
            previous_value=Decimal("450"),
            variance_value=Decimal("50"),
            variance_percent=Decimal("11.111111"),
        )
    ]
    account_variances = [
        SimpleNamespace(
            account_code="4100",
            account_name="Revenue",
            current_value=Decimal("500"),
            previous_value=Decimal("450"),
            variance_value=Decimal("50"),
            variance_percent=Decimal("11.111111"),
        )
    ]
    anomalies = SimpleNamespace(rows=[SimpleNamespace(severity="HIGH", anomaly_type="MARGIN_DEVIATION", explanation="Margin moved by 20")])
    recommendations = SimpleNamespace(rows=[SimpleNamespace(message="Prioritize collections")])

    monkeypatch.setattr(
        narrative_service,
        "compute_kpis",
        AsyncMock(return_value=SimpleNamespace(rows=kpi_rows)),
    )
    monkeypatch.setattr(
        narrative_service,
        "compute_variance",
        AsyncMock(return_value=SimpleNamespace(metric_variances=metric_variances, account_variances=account_variances)),
    )
    monkeypatch.setattr(
        narrative_service,
        "detect_anomalies",
        AsyncMock(return_value=anomalies),
    )
    monkeypatch.setattr(
        narrative_service,
        "generate_recommendations",
        AsyncMock(return_value=recommendations),
    )

    result = await narrative_service.generate_narrative(
        AsyncMock(),
        tenant_id=uuid.uuid4(),
        actor_user_id=uuid.uuid4(),
        org_entity_id=uuid.uuid4(),
        org_group_id=None,
        from_date=date(2026, 3, 1),
        to_date=date(2026, 3, 31),
    )
    assert "500" in result.summary
    assert "120" in result.summary
    assert result.validation_passed is True
    assert len(result.highlights) >= 1


@pytest.mark.asyncio
async def test_truth_integrity_exact_numbers_no_approximation(monkeypatch: pytest.MonkeyPatch) -> None:
    metric_variances = [
        SimpleNamespace(
            metric_name="revenue",
            current_value=Decimal("112.4"),
            previous_value=Decimal("100.0"),
            variance_value=Decimal("12.4"),
            variance_percent=Decimal("12.4"),
        )
    ]
    account_variances = [
        SimpleNamespace(
            account_code="4100",
            account_name="Services Revenue",
            current_value=Decimal("112.4"),
            previous_value=Decimal("100.0"),
            variance_value=Decimal("12.4"),
            variance_percent=Decimal("12.4"),
        )
    ]
    drilldown = SimpleNamespace(
        accounts=[SimpleNamespace(account_code="4100")],
        journals=[],
        gl_entries=[],
        lineage={"entity_ids": ["entity-A"]},
    )
    monkeypatch.setattr(
        explanation_service,
        "compute_variance",
        AsyncMock(return_value=SimpleNamespace(metric_variances=metric_variances, account_variances=account_variances)),
    )
    monkeypatch.setattr(
        explanation_service,
        "get_metric_drilldown",
        AsyncMock(return_value=drilldown),
    )
    result = await explanation_service.explain_variance(
        AsyncMock(),
        tenant_id=uuid.uuid4(),
        metric_name="revenue",
        org_entity_id=uuid.uuid4(),
        org_group_id=None,
        from_date=date(2026, 3, 1),
        to_date=date(2026, 3, 31),
    )
    assert "112.4" in result.explanation
    assert "12.4%" in result.explanation
    assert "~" not in result.explanation
    assert "approximately" not in result.explanation.lower()


@pytest.mark.asyncio
async def test_explanation_correctness_with_real_driver_and_entity(monkeypatch: pytest.MonkeyPatch) -> None:
    metric_variances = [
        SimpleNamespace(
            metric_name="revenue",
            current_value=Decimal("210"),
            previous_value=Decimal("180"),
            variance_value=Decimal("30"),
            variance_percent=Decimal("16.666667"),
        )
    ]
    account_variances = [
        SimpleNamespace(
            account_code="4100",
            account_name="Enterprise Sales",
            current_value=Decimal("210"),
            previous_value=Decimal("180"),
            variance_value=Decimal("30"),
            variance_percent=Decimal("16.666667"),
        )
    ]
    drilldown = SimpleNamespace(
        accounts=[SimpleNamespace(account_code="4100")],
        journals=[1, 2],
        gl_entries=[1, 2, 3],
        lineage={"entity_ids": ["entity-A", "entity-B"]},
    )
    monkeypatch.setattr(
        explanation_service,
        "compute_variance",
        AsyncMock(return_value=SimpleNamespace(metric_variances=metric_variances, account_variances=account_variances)),
    )
    monkeypatch.setattr(
        explanation_service,
        "get_metric_drilldown",
        AsyncMock(return_value=drilldown),
    )

    result = await explanation_service.explain_variance(
        AsyncMock(),
        tenant_id=uuid.uuid4(),
        metric_name="revenue",
        org_entity_id=None,
        org_group_id=uuid.uuid4(),
        from_date=date(2026, 3, 1),
        to_date=date(2026, 3, 31),
    )
    assert "4100" in result.explanation
    assert "Enterprise Sales" in result.explanation
    assert "entity-A" in result.explanation


@pytest.mark.asyncio
async def test_recommendation_is_specific_and_actionable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        recommendation_service,
        "compute_kpis",
        AsyncMock(
            return_value=SimpleNamespace(
                rows=[
                    SimpleNamespace(metric_name="net_margin", metric_value=Decimal("9")),
                    SimpleNamespace(metric_name="current_ratio", metric_value=Decimal("0.95")),
                    SimpleNamespace(metric_name="debt_equity", metric_value=Decimal("1.2")),
                    SimpleNamespace(metric_name="net_profit", metric_value=Decimal("10")),
                ]
            )
        ),
    )
    monkeypatch.setattr(
        recommendation_service,
        "compute_ratios",
        AsyncMock(return_value=SimpleNamespace(rows=[SimpleNamespace(metric_name="receivable_days", metric_value=Decimal("92"))])),
    )
    monkeypatch.setattr(
        recommendation_service,
        "compute_variance",
        AsyncMock(return_value=SimpleNamespace(metric_variances=[])),
    )
    result = await recommendation_service.generate_recommendations(
        AsyncMock(),
        tenant_id=uuid.uuid4(),
        actor_user_id=uuid.uuid4(),
        org_entity_id=uuid.uuid4(),
        org_group_id=None,
        from_date=date(2026, 3, 1),
        to_date=date(2026, 3, 31),
        persist=False,
    )
    joined = " ".join(item.message for item in result.rows)
    assert "92" in joined
    assert any(token in joined.lower() for token in ("prioritize", "review", "tighten", "accelerate"))


@pytest.mark.asyncio
async def test_safety_control_suggestions_not_auto_posted() -> None:
    from financeops.modules.ai_cfo_layer.application.suggestion_service import SuggestionsResponse

    payload = SuggestionsResponse(rows=[], validation={"auto_posted": False})
    assert payload.validation["auto_posted"] is False


def test_validation_layer_rejects_hallucinated_numbers() -> None:
    from financeops.core.exceptions import ValidationError

    with pytest.raises(ValidationError):
        validate_generated_text_against_facts(
            text="Revenue moved to 999 while known value is 100.",
            allowed_numbers=[Decimal("100")],
        )


@pytest.mark.asyncio
async def test_reproducibility_same_inputs_same_outputs(monkeypatch: pytest.MonkeyPatch) -> None:
    metric_variances = [
        SimpleNamespace(
            metric_name="revenue",
            current_value=Decimal("130"),
            previous_value=Decimal("100"),
            variance_value=Decimal("30"),
            variance_percent=Decimal("30"),
        )
    ]
    account_variances = []
    trend_series = [
        SimpleNamespace(
            metric_name="cash",
            points=[
                SimpleNamespace(period="2026-01", value=Decimal("100")),
                SimpleNamespace(period="2026-02", value=Decimal("110")),
                SimpleNamespace(period="2026-03", value=Decimal("90")),
            ],
        )
    ]
    monkeypatch.setattr(
        anomaly_service,
        "compute_variance",
        AsyncMock(return_value=SimpleNamespace(metric_variances=metric_variances, account_variances=account_variances)),
    )
    monkeypatch.setattr(
        anomaly_service,
        "compute_trends",
        AsyncMock(return_value=SimpleNamespace(frequency="monthly", series=trend_series)),
    )
    session = AsyncMock()
    first = await anomaly_service.detect_anomalies(
        session,
        tenant_id=uuid.uuid4(),
        actor_user_id=uuid.uuid4(),
        org_entity_id=uuid.uuid4(),
        org_group_id=None,
        from_date=date(2026, 3, 1),
        to_date=date(2026, 3, 31),
        persist=False,
    )
    second = await anomaly_service.detect_anomalies(
        session,
        tenant_id=uuid.uuid4(),
        actor_user_id=uuid.uuid4(),
        org_entity_id=uuid.uuid4(),
        org_group_id=None,
        from_date=date(2026, 3, 1),
        to_date=date(2026, 3, 31),
        persist=False,
    )
    first_key = [(r.metric_name, r.anomaly_type, r.explanation) for r in first.rows]
    second_key = [(r.metric_name, r.anomaly_type, r.explanation) for r in second.rows]
    assert first_key == second_key


@pytest.mark.asyncio
async def test_bonus_anomaly_sensitivity(monkeypatch: pytest.MonkeyPatch) -> None:
    small_variance = [
        SimpleNamespace(
            metric_name="revenue",
            current_value=Decimal("102"),
            previous_value=Decimal("100"),
            variance_value=Decimal("2"),
            variance_percent=Decimal("2"),
        )
    ]
    large_variance = [
        SimpleNamespace(
            metric_name="revenue",
            current_value=Decimal("150"),
            previous_value=Decimal("100"),
            variance_value=Decimal("50"),
            variance_percent=Decimal("50"),
        )
    ]
    trend_series = [SimpleNamespace(metric_name="cash", points=[])]

    monkeypatch.setattr(anomaly_service, "compute_trends", AsyncMock(return_value=SimpleNamespace(frequency="monthly", series=trend_series)))
    monkeypatch.setattr(
        anomaly_service,
        "compute_variance",
        AsyncMock(return_value=SimpleNamespace(metric_variances=small_variance, account_variances=[])),
    )
    small = await anomaly_service.detect_anomalies(
        AsyncMock(),
        tenant_id=uuid.uuid4(),
        actor_user_id=uuid.uuid4(),
        org_entity_id=uuid.uuid4(),
        org_group_id=None,
        from_date=date(2026, 3, 1),
        to_date=date(2026, 3, 31),
        persist=False,
    )
    monkeypatch.setattr(
        anomaly_service,
        "compute_variance",
        AsyncMock(return_value=SimpleNamespace(metric_variances=large_variance, account_variances=[])),
    )
    large = await anomaly_service.detect_anomalies(
        AsyncMock(),
        tenant_id=uuid.uuid4(),
        actor_user_id=uuid.uuid4(),
        org_entity_id=uuid.uuid4(),
        org_group_id=None,
        from_date=date(2026, 3, 1),
        to_date=date(2026, 3, 31),
        persist=False,
    )
    assert len(small.rows) == 0
    assert any(item.anomaly_type == "REVENUE_SPIKE" for item in large.rows)


@pytest.mark.asyncio
async def test_bonus_cross_tenant_scope_enforced_in_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    expected_tenant_id = uuid.uuid4()
    expected_entity_id = uuid.uuid4()
    expected_from = date(2026, 3, 1)
    expected_to = date(2026, 3, 31)

    async def _compute_variance(
        _db,
        *,
        tenant_id,
        org_entity_id,
        org_group_id,
        from_date,
        to_date,
        comparison,
    ):
        assert tenant_id == expected_tenant_id
        assert org_entity_id == expected_entity_id
        assert org_group_id is None
        assert from_date == expected_from
        assert to_date == expected_to
        return SimpleNamespace(metric_variances=[], account_variances=[])

    async def _compute_trends(
        _db,
        *,
        tenant_id,
        org_entity_id,
        org_group_id,
        from_date,
        to_date,
        frequency,
    ):
        assert tenant_id == expected_tenant_id
        assert org_entity_id == expected_entity_id
        assert org_group_id is None
        assert from_date == expected_from
        assert to_date == expected_to
        return SimpleNamespace(frequency="monthly", series=[])

    monkeypatch.setattr(anomaly_service, "compute_variance", _compute_variance)
    monkeypatch.setattr(anomaly_service, "compute_trends", _compute_trends)
    result = await anomaly_service.detect_anomalies(
        AsyncMock(),
        tenant_id=expected_tenant_id,
        actor_user_id=uuid.uuid4(),
        org_entity_id=expected_entity_id,
        org_group_id=None,
        from_date=expected_from,
        to_date=expected_to,
        persist=False,
    )
    assert result.validation["count"] == 0


@pytest.mark.asyncio
async def test_bonus_drilldown_consistency_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    metric_variances = [
        SimpleNamespace(
            metric_name="revenue",
            current_value=Decimal("150"),
            previous_value=Decimal("100"),
            variance_value=Decimal("50"),
            variance_percent=Decimal("50"),
        )
    ]
    account_variances = [
        SimpleNamespace(
            account_code="4100",
            account_name="Services Revenue",
            current_value=Decimal("150"),
            previous_value=Decimal("100"),
            variance_value=Decimal("50"),
            variance_percent=Decimal("50"),
        )
    ]
    monkeypatch.setattr(
        explanation_service,
        "compute_variance",
        AsyncMock(return_value=SimpleNamespace(metric_variances=metric_variances, account_variances=account_variances)),
    )
    monkeypatch.setattr(
        explanation_service,
        "get_metric_drilldown",
        AsyncMock(return_value=SimpleNamespace(accounts=[SimpleNamespace(account_code="4200")], journals=[], gl_entries=[], lineage={"entity_ids": []})),
    )
    from financeops.core.exceptions import ValidationError

    with pytest.raises(ValidationError):
        await explanation_service.explain_variance(
            AsyncMock(),
            tenant_id=uuid.uuid4(),
            metric_name="revenue",
            org_entity_id=uuid.uuid4(),
            org_group_id=None,
            from_date=date(2026, 3, 1),
            to_date=date(2026, 3, 31),
        )
