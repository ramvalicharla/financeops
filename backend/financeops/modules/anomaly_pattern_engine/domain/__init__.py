from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any


@dataclass(frozen=True)
class DefinitionVersionTokenInput:
    rows: list[dict[str, Any]]


@dataclass(frozen=True)
class AnomalyRunTokenInput:
    tenant_id: uuid.UUID
    organisation_id: uuid.UUID
    reporting_period: date
    anomaly_definition_version_token: str
    pattern_rule_version_token: str
    persistence_rule_version_token: str
    correlation_rule_version_token: str
    statistical_rule_version_token: str
    source_metric_run_ids: list[str]
    source_variance_run_ids: list[str]
    source_trend_run_ids: list[str]
    source_risk_run_ids: list[str]
    source_reconciliation_session_ids: list[str]
    status: str
