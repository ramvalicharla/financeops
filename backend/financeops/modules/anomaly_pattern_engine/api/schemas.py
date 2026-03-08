from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class AnomalyDefinitionCreateRequest(BaseModel):
    organisation_id: uuid.UUID
    anomaly_code: str
    anomaly_name: str
    anomaly_domain: str
    signal_selector_json: dict[str, Any] = Field(default_factory=dict)
    definition_json: dict[str, Any] = Field(default_factory=dict)
    effective_from: date
    effective_to: date | None = None
    supersedes_id: uuid.UUID | None = None
    status: str = "candidate"


class AnomalyPatternRuleCreateRequest(BaseModel):
    organisation_id: uuid.UUID
    rule_code: str
    rule_name: str
    pattern_signature_json: dict[str, Any] = Field(default_factory=dict)
    classification_behavior_json: dict[str, Any] = Field(default_factory=dict)
    effective_from: date
    supersedes_id: uuid.UUID | None = None
    status: str = "candidate"


class AnomalyPersistenceRuleCreateRequest(BaseModel):
    organisation_id: uuid.UUID
    rule_code: str
    rule_name: str
    rolling_window: int
    recurrence_threshold: int
    escalation_logic_json: dict[str, Any] = Field(default_factory=dict)
    effective_from: date
    supersedes_id: uuid.UUID | None = None
    status: str = "candidate"


class AnomalyCorrelationRuleCreateRequest(BaseModel):
    organisation_id: uuid.UUID
    rule_code: str
    rule_name: str
    correlation_window: int
    min_signal_count: int
    correlation_logic_json: dict[str, Any] = Field(default_factory=dict)
    effective_from: date
    supersedes_id: uuid.UUID | None = None
    status: str = "candidate"


class AnomalyStatisticalRuleCreateRequest(BaseModel):
    organisation_id: uuid.UUID
    rule_code: str
    rule_name: str
    rolling_window: int
    baseline_type: str
    z_threshold: Decimal
    regime_shift_threshold_pct: Decimal
    seasonal_period: int | None = None
    seasonal_adjustment_flag: bool = False
    benchmark_group_id: str | None = None
    configuration_json: dict[str, Any] = Field(default_factory=dict)
    effective_from: date
    supersedes_id: uuid.UUID | None = None
    status: str = "candidate"


class AnomalyRunCreateRequest(BaseModel):
    organisation_id: uuid.UUID
    reporting_period: date
    source_metric_run_ids: list[uuid.UUID]
    source_variance_run_ids: list[uuid.UUID]
    source_trend_run_ids: list[uuid.UUID] = Field(default_factory=list)
    source_risk_run_ids: list[uuid.UUID] = Field(default_factory=list)
    source_reconciliation_session_ids: list[uuid.UUID] = Field(default_factory=list)


class AnomalyRunCreateResponse(BaseModel):
    run_id: uuid.UUID
    run_token: str
    status: str
    idempotent: bool


class AnomalyRunExecuteResponse(BaseModel):
    run_id: uuid.UUID
    run_token: str
    status: str
    result_count: int
    signal_count: int
    rollforward_count: int
    evidence_count: int
    idempotent: bool
