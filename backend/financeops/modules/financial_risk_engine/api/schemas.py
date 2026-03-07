from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class RiskDependencyIn(BaseModel):
    dependency_type: str
    depends_on_risk_definition_id: uuid.UUID | None = None
    signal_reference_code: str | None = None
    propagation_factor: Decimal = Decimal("1")
    amplification_rule_json: dict[str, Any] = Field(default_factory=dict)
    attenuation_rule_json: dict[str, Any] = Field(default_factory=dict)
    cap_limit: Decimal = Decimal("1")


class RiskDefinitionCreateRequest(BaseModel):
    organisation_id: uuid.UUID
    risk_code: str
    risk_name: str
    risk_domain: str
    signal_selector_json: dict[str, Any] = Field(default_factory=dict)
    definition_json: dict[str, Any] = Field(default_factory=dict)
    effective_from: date
    effective_to: date | None = None
    supersedes_id: uuid.UUID | None = None
    status: str = "candidate"
    dependencies: list[RiskDependencyIn] = Field(default_factory=list)


class RiskWeightCreateRequest(BaseModel):
    organisation_id: uuid.UUID
    weight_code: str
    risk_code: str
    scope_type: str = "global"
    scope_value: str | None = None
    weight_value: Decimal
    board_critical_override: bool = False
    configuration_json: dict[str, Any] = Field(default_factory=dict)
    effective_from: date
    supersedes_id: uuid.UUID | None = None
    status: str = "candidate"


class RiskMaterialityRuleCreateRequest(BaseModel):
    organisation_id: uuid.UUID
    rule_code: str
    rule_name: str
    threshold_json: dict[str, Any] = Field(default_factory=dict)
    severity_mapping_json: dict[str, Any] = Field(default_factory=dict)
    propagation_behavior_json: dict[str, Any] = Field(default_factory=dict)
    escalation_rule_json: dict[str, Any] = Field(default_factory=dict)
    effective_from: date
    supersedes_id: uuid.UUID | None = None
    status: str = "candidate"


class RiskRunCreateRequest(BaseModel):
    organisation_id: uuid.UUID
    reporting_period: date
    source_metric_run_ids: list[uuid.UUID]
    source_variance_run_ids: list[uuid.UUID]
    source_trend_run_ids: list[uuid.UUID] = Field(default_factory=list)
    source_reconciliation_session_ids: list[uuid.UUID] = Field(default_factory=list)


class RiskRunCreateResponse(BaseModel):
    run_id: uuid.UUID
    run_token: str
    status: str
    idempotent: bool


class RiskRunExecuteResponse(BaseModel):
    run_id: uuid.UUID
    run_token: str
    status: str
    result_count: int
    signal_count: int
    rollforward_count: int
    evidence_count: int
    idempotent: bool
