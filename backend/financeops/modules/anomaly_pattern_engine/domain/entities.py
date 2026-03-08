from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from financeops.modules.anomaly_pattern_engine.domain.enums import (
    PersistenceClassification,
    SeverityLevel,
)


@dataclass(frozen=True)
class ComputedAnomaly:
    anomaly_code: str
    anomaly_name: str
    anomaly_domain: str
    anomaly_score: Decimal
    z_score: Decimal
    severity: SeverityLevel
    persistence_classification: PersistenceClassification
    correlation_flag: bool
    materiality_elevated: bool
    risk_elevated: bool
    board_flag: bool
    confidence_score: Decimal
    seasonal_adjustment_flag: bool
    seasonal_normalized_value: Decimal | None
    benchmark_group_id: str | None
    benchmark_baseline_value: Decimal | None
    benchmark_deviation_score: Decimal | None
    source_summary_json: dict[str, Any]


@dataclass(frozen=True)
class AnomalySignal:
    signal_type: str
    signal_ref: str
    contribution_weight: Decimal
    contribution_score: Decimal
    signal_payload_json: dict[str, Any]


@dataclass(frozen=True)
class AnomalyRollforward:
    event_type: str
    event_payload_json: dict[str, Any]
