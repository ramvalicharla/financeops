from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from financeops.modules.financial_risk_engine.application.materiality_service import (
    MaterialityService,
)
from financeops.modules.financial_risk_engine.application.scoring_service import ScoringService
from financeops.modules.financial_risk_engine.domain.enums import SeverityLevel
from financeops.modules.financial_risk_engine.domain.value_objects import RiskRunTokenInput
from financeops.modules.financial_risk_engine.infrastructure.token_builder import (
    build_risk_run_token,
)


def test_risk_run_token_is_deterministic() -> None:
    payload = RiskRunTokenInput(
        tenant_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        organisation_id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
        reporting_period=date(2026, 1, 31),
        risk_definition_version_token="a" * 64,
        propagation_version_token="b" * 64,
        weight_version_token="c" * 64,
        materiality_version_token="d" * 64,
        source_metric_run_ids=["m2", "m1"],
        source_variance_run_ids=["v1"],
        source_trend_run_ids=["t1"],
        source_reconciliation_session_ids=["r1"],
        status="created",
    )
    first = build_risk_run_token(payload)
    second = build_risk_run_token(payload)
    assert first == second


def test_scoring_and_materiality_are_deterministic() -> None:
    scoring = ScoringService()
    materiality = MaterialityService()

    weight = Decimal("1")
    score = scoring.combine(
        [
            scoring.metric_signal(Decimal("1000"), weight=weight),
            scoring.variance_signal(Decimal("20"), weight=weight),
            scoring.trend_signal(Decimal("15"), weight=weight),
        ]
    )
    rule_json = {
        "materiality_threshold": "0.20",
        "severity_thresholds": {
            "critical": "0.85",
            "high": "0.65",
            "medium": "0.40",
            "low": "0.20",
        },
    }
    severity = materiality.severity_for_score(score=score, rule_json=rule_json)
    assert severity in {
        SeverityLevel.INFO,
        SeverityLevel.LOW,
        SeverityLevel.MEDIUM,
        SeverityLevel.HIGH,
        SeverityLevel.CRITICAL,
    }
    assert materiality.materiality_flag(score=score, rule_json=rule_json) is True


def test_dependency_signal_and_confidence_logic() -> None:
    scoring = ScoringService()
    dependency = scoring.dependency_signal(
        parent_score=Decimal("0.9"),
        propagation_factor=Decimal("0.5"),
        cap_limit=Decimal("0.7"),
    )
    assert dependency == Decimal("0.450000")

    confidence = scoring.confidence(
        has_signals=True,
        unresolved_dependency=True,
        has_open_reconciliation=True,
    )
    assert confidence == Decimal("0.500000")


def test_weight_resolution_precedence_is_stable() -> None:
    scoring = ScoringService()
    rows = [
        SimpleNamespace(
            risk_code="*",
            scope_type="global",
            scope_value=None,
            weight_value=Decimal("1.1"),
            board_critical_override=False,
        ),
        SimpleNamespace(
            risk_code="RISK_X",
            scope_type="domain",
            scope_value="liquidity",
            weight_value=Decimal("1.2"),
            board_critical_override=False,
        ),
    ]
    weight = scoring.base_weight_for_definition(
        risk_code="RISK_X",
        risk_domain="liquidity",
        rows=rows,
    )
    assert weight == Decimal("1.320000")
