from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from financeops.modules.financial_risk_engine.domain.enums import (
    PersistenceState,
    SeverityLevel,
)


@dataclass(frozen=True)
class ComputedRisk:
    risk_code: str
    risk_name: str
    risk_domain: str
    risk_score: Decimal
    severity: SeverityLevel
    confidence_score: Decimal
    materiality_flag: bool
    board_attention_flag: bool
    persistence_state: PersistenceState
    unresolved_dependency_flag: bool
    source_summary_json: dict[str, Any]


@dataclass(frozen=True)
class RiskSignal:
    signal_type: str
    signal_ref: str
    contribution_weight: Decimal
    contribution_score: Decimal
    signal_payload_json: dict[str, Any]


@dataclass(frozen=True)
class RiskRollforward:
    event_type: str
    event_payload_json: dict[str, Any]
