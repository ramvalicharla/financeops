from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class MetricDefinitionComponentIn(BaseModel):
    component_code: str
    source_type: str
    source_key: str
    operator: str = "add"
    weight: Decimal = Decimal("1")
    ordinal_position: int
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class MetricDefinitionCreateRequest(BaseModel):
    organisation_id: uuid.UUID
    definition_code: str
    definition_name: str
    metric_code: str
    formula_type: str
    formula_json: dict[str, Any] = Field(default_factory=dict)
    unit_type: str = "amount"
    directionality: str = "neutral"
    effective_from: date
    supersedes_id: uuid.UUID | None = None
    status: str = "candidate"
    components: list[MetricDefinitionComponentIn] = Field(default_factory=list)


class VarianceDefinitionCreateRequest(BaseModel):
    organisation_id: uuid.UUID
    definition_code: str
    definition_name: str
    metric_code: str
    comparison_type: str
    configuration_json: dict[str, Any] = Field(default_factory=dict)
    effective_from: date
    supersedes_id: uuid.UUID | None = None
    status: str = "candidate"


class TrendDefinitionCreateRequest(BaseModel):
    organisation_id: uuid.UUID
    definition_code: str
    definition_name: str
    metric_code: str
    trend_type: str
    window_size: int
    configuration_json: dict[str, Any] = Field(default_factory=dict)
    effective_from: date
    supersedes_id: uuid.UUID | None = None
    status: str = "candidate"


class MaterialityRuleCreateRequest(BaseModel):
    organisation_id: uuid.UUID
    definition_code: str
    definition_name: str
    rule_json: dict[str, Any] = Field(default_factory=dict)
    effective_from: date
    supersedes_id: uuid.UUID | None = None
    status: str = "candidate"


class RunCreateRequest(BaseModel):
    organisation_id: uuid.UUID
    reporting_period: date
    scope_json: dict[str, Any] = Field(default_factory=dict)
    mis_snapshot_id: uuid.UUID | None = None
    payroll_run_id: uuid.UUID | None = None
    gl_run_id: uuid.UUID | None = None
    reconciliation_session_id: uuid.UUID | None = None
    payroll_gl_reconciliation_run_id: uuid.UUID | None = None


class RunCreateResponse(BaseModel):
    run_id: uuid.UUID
    run_token: str
    status: str
    idempotent: bool


class RunExecuteResponse(BaseModel):
    run_id: uuid.UUID
    run_token: str
    status: str
    metric_count: int
    variance_count: int
    trend_count: int
    idempotent: bool


class RunSummaryResponse(BaseModel):
    run_id: uuid.UUID
    run_token: str
    status: str
    metric_count: int
    variance_count: int
    trend_count: int
    evidence_count: int
