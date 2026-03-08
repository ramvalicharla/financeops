from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest

from financeops.modules.anomaly_pattern_engine.application.correlation_service import (
    CorrelationService,
)
from financeops.modules.anomaly_pattern_engine.application.materiality_service import (
    MaterialityService,
)
from financeops.modules.anomaly_pattern_engine.application.persistence_service import (
    PersistenceService,
)
from financeops.modules.anomaly_pattern_engine.application.scoring_service import (
    ScoringService,
)
from financeops.modules.anomaly_pattern_engine.application.statistical_service import (
    StatisticalService,
)
from financeops.modules.anomaly_pattern_engine.domain.enums import (
    PersistenceClassification,
    SeverityLevel,
)
from financeops.modules.anomaly_pattern_engine.domain.value_objects import (
    AnomalyRunTokenInput,
)
from financeops.modules.anomaly_pattern_engine.infrastructure.token_builder import (
    build_anomaly_run_token,
)


def test_anomaly_run_token_is_deterministic() -> None:
    payload = AnomalyRunTokenInput(
        tenant_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        organisation_id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
        reporting_period=date(2026, 1, 31),
        anomaly_definition_version_token="a" * 64,
        pattern_rule_version_token="b" * 64,
        persistence_rule_version_token="c" * 64,
        correlation_rule_version_token="d" * 64,
        statistical_rule_version_token="e" * 64,
        source_metric_run_ids=["m2", "m1"],
        source_variance_run_ids=["v2", "v1"],
        source_trend_run_ids=["t1"],
        source_risk_run_ids=["r1"],
        source_reconciliation_session_ids=["s1"],
        status="created",
    )
    assert build_anomaly_run_token(payload) == build_anomaly_run_token(payload)


def test_zscore_and_rolling_computation_are_stable() -> None:
    service = StatisticalService()
    values = [Decimal("1"), Decimal("2"), Decimal("3"), Decimal("4")]
    assert service.rolling_window(values, window=3) == [
        Decimal("2"),
        Decimal("3"),
        Decimal("4"),
    ]
    assert service.rolling_mean(values, window=3) == Decimal("3.000000")
    assert service.rolling_std(values, window=3) == Decimal("0.816497")
    assert service.rolling_median(values, window=3) == Decimal("3.000000")
    assert service.rolling_pct_change(values, window=3) == Decimal("1.000000")
    z = service.z_score(
        current_value=Decimal("4"),
        baseline_mean=Decimal("3"),
        baseline_std=Decimal("0.816497"),
    )
    assert z == Decimal("1.224744")
    assert (
        service.regime_shift_flag(
            values=[
                Decimal("10"),
                Decimal("10"),
                Decimal("10"),
                Decimal("20"),
                Decimal("20"),
                Decimal("20"),
            ],
            window=3,
            threshold_pct=Decimal("0.500000"),
        )
        is True
    )
    with pytest.raises(ValueError, match="Zero std-dev baseline"):
        service.z_score(
            current_value=Decimal("1"),
            baseline_mean=Decimal("1"),
            baseline_std=Decimal("0"),
        )


def test_persistence_classification_transitions_are_deterministic() -> None:
    service = PersistenceService()
    assert (
        service.classify(
            prior_severity=None,
            current_severity=SeverityLevel.MEDIUM,
            recurrence_count=0,
            recurrence_threshold=2,
        )
        == PersistenceClassification.FIRST_DETECTED
    )
    assert (
        service.classify(
            prior_severity=SeverityLevel.INFO.value,
            current_severity=SeverityLevel.LOW,
            recurrence_count=1,
            recurrence_threshold=2,
        )
        == PersistenceClassification.REOPENED
    )
    assert (
        service.classify(
            prior_severity=SeverityLevel.HIGH.value,
            current_severity=SeverityLevel.INFO,
            recurrence_count=1,
            recurrence_threshold=2,
        )
        == PersistenceClassification.RESOLVED
    )
    assert (
        service.classify(
            prior_severity=SeverityLevel.MEDIUM.value,
            current_severity=SeverityLevel.HIGH,
            recurrence_count=1,
            recurrence_threshold=2,
        )
        == PersistenceClassification.ESCALATING
    )
    assert (
        service.classify(
            prior_severity=SeverityLevel.HIGH.value,
            current_severity=SeverityLevel.HIGH,
            recurrence_count=2,
            recurrence_threshold=2,
        )
        == PersistenceClassification.SUSTAINED
    )


def test_correlation_and_materiality_classification_are_deterministic() -> None:
    correlation = CorrelationService()
    assert (
        correlation.correlation_flag(
            signal_scores=[Decimal("0.60"), Decimal("0.51"), Decimal("0.10")],
            min_signal_count=2,
        )
        is True
    )
    assert (
        correlation.correlation_flag(
            signal_scores=[Decimal("0.60"), Decimal("0.10"), Decimal("0.05")],
            min_signal_count=2,
        )
        is False
    )
    with pytest.raises(ValueError, match="min_signal_count"):
        correlation.correlation_flag(signal_scores=[Decimal("1")], min_signal_count=0)

    scoring = ScoringService()
    materiality = MaterialityService()
    thresholds = {
        "moderate_z": Decimal("1.5"),
        "high_z": Decimal("2.0"),
        "extreme_z": Decimal("3.0"),
        "material_score": Decimal("0.5"),
    }
    score = scoring.normalized_score_from_z(Decimal("2.4"))
    severity = materiality.severity_from_z(z_score=Decimal("2.4"), thresholds=thresholds)
    elevated = materiality.elevate_severity(
        current=severity,
        risk_elevated=True,
        materiality_elevated=materiality.materiality_flag(anomaly_score=score, thresholds=thresholds),
        board_critical=False,
    )
    assert score == Decimal("0.800000")
    assert severity == SeverityLevel.HIGH
    assert elevated == SeverityLevel.HIGH
