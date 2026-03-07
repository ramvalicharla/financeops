from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from financeops.modules.ratio_variance_engine.application.materiality_service import (
    MaterialityService,
)
from financeops.modules.ratio_variance_engine.application.metric_definition_service import (
    MetricDefinitionService,
)
from financeops.modules.ratio_variance_engine.application.trend_service import TrendService
from financeops.modules.ratio_variance_engine.application.variance_service import (
    VarianceService,
)
from financeops.modules.ratio_variance_engine.domain.enums import FavorableStatus
from financeops.modules.ratio_variance_engine.domain.value_objects import MetricRunTokenInput
from financeops.modules.ratio_variance_engine.infrastructure.token_builder import (
    build_metric_run_token,
)


def _definition(metric_code: str, formula_type: str = "sum") -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        definition_code=f"DEF_{metric_code}",
        metric_code=metric_code,
        formula_type=formula_type,
        formula_json={},
        unit_type="amount",
        directionality="higher_is_better",
        status="active",
        effective_from=date(2026, 1, 1),
    )


def _component(
    source_type: str,
    source_key: str,
    ordinal: int,
    operator: str = "add",
    weight: str = "1",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        component_code=f"C{ordinal}",
        source_type=source_type,
        source_key=source_key,
        operator=operator,
        weight=Decimal(weight),
        ordinal_position=ordinal,
        metadata_json={},
    )


def test_metric_formula_resolution_and_ratio_correctness() -> None:
    service = MetricDefinitionService()
    materiality = MaterialityService()
    revenue_def = _definition("revenue", "sum")
    margin_def = _definition("gross_margin_pct", "ratio")
    components = {
        str(revenue_def.id): [_component("payroll_metric", "gross_pay", 1)],
        str(margin_def.id): [
            _component("metric_ref", "revenue", 1),
            _component("constant", "2000", 2),
        ],
    }
    output = service.compute_metrics(
        definitions=[revenue_def, margin_def],
        components_by_definition=components,
        source_values={"payroll_metric": {"gross_pay": Decimal("1000")}},
        rule_json={"absolute_threshold": "1"},
        scope_json={"entity": "LE1"},
        materiality_service=materiality,
    )
    by_code = {row.metric_code: row for row in output}
    assert by_code["revenue"].metric_value == Decimal("1000.000000")
    assert by_code["gross_margin_pct"].metric_value == Decimal("50.000000")


def test_variance_bps_and_directionality_logic() -> None:
    service = VarianceService()
    materiality = MaterialityService()
    definition = SimpleNamespace(
        id=uuid.uuid4(),
        definition_code="VAR_REV",
        metric_code="revenue",
        comparison_type="mom_abs_pct",
        configuration_json={},
        status="active",
        effective_from=date(2026, 1, 1),
    )
    rows = service.compute_variances(
        definitions=[definition],
        metric_values={"revenue": Decimal("120")},
        prior_series_lookup={"revenue": [(date(2025, 12, 31), Decimal("100"))]},
        scope_json={"entity": "LE1"},
        materiality_rule_json={"absolute_threshold": "5", "percentage_threshold": "5", "basis_points_threshold": "100"},
        directionality_by_metric={"revenue": "higher_is_better"},
        materiality_service=materiality,
    )
    assert rows[0].variance_abs == Decimal("20.000000")
    assert rows[0].variance_bps == Decimal("200000.000000")
    assert rows[0].favorable_status == FavorableStatus.FAVORABLE


def test_trend_logic_rolling_average_and_direction() -> None:
    service = TrendService()
    definition = SimpleNamespace(
        id=uuid.uuid4(),
        definition_code="TRD_REV",
        metric_code="revenue",
        trend_type="rolling_average",
        window_size=3,
        configuration_json={},
        status="active",
        effective_from=date(2026, 1, 1),
    )
    rows = service.compute_trends(
        definitions=[definition],
        metric_values={"revenue": Decimal("120")},
        prior_series_lookup={
            "revenue": [
                (date(2025, 12, 31), Decimal("100")),
                (date(2025, 11, 30), Decimal("80")),
            ]
        },
    )
    assert rows[0].trend_value == Decimal("100.000000")
    assert rows[0].trend_direction == "up"


def test_materiality_flag_logic() -> None:
    service = MaterialityService()
    assert service.metric_materiality(
        metric_code="revenue",
        value=Decimal("10"),
        rule_json={"absolute_threshold": "5"},
    )
    assert service.variance_materiality(
        metric_code="revenue",
        variance_abs=Decimal("2"),
        variance_pct=Decimal("10"),
        variance_bps=Decimal("50"),
        rule_json={"absolute_threshold": "5", "percentage_threshold": "5", "basis_points_threshold": "100"},
    )


def test_run_token_determinism() -> None:
    payload = MetricRunTokenInput(
        tenant_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        organisation_id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
        reporting_period=date(2026, 1, 31),
        scope_json={"entity": "LE1"},
        mis_snapshot_id=None,
        payroll_run_id=uuid.UUID("33333333-3333-3333-3333-333333333333"),
        gl_run_id=uuid.UUID("44444444-4444-4444-4444-444444444444"),
        reconciliation_session_id=None,
        payroll_gl_reconciliation_run_id=None,
        metric_definition_version_token="a" * 64,
        variance_definition_version_token="b" * 64,
        trend_definition_version_token="c" * 64,
        materiality_rule_version_token="d" * 64,
        input_signature_hash="e" * 64,
    )
    first = build_metric_run_token(payload, status="created")
    second = build_metric_run_token(payload, status="created")
    assert first == second
