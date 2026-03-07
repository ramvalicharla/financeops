from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from pydantic import BaseModel, Field


class MappingCreateRequest(BaseModel):
    organisation_id: uuid.UUID
    mapping_code: str
    mapping_name: str
    payroll_metric_code: str
    gl_account_selector_json: dict[str, Any] = Field(default_factory=dict)
    cost_center_rule_json: dict[str, Any] = Field(default_factory=dict)
    department_rule_json: dict[str, Any] = Field(default_factory=dict)
    entity_rule_json: dict[str, Any] = Field(default_factory=dict)
    effective_from: date
    supersedes_id: uuid.UUID | None = None
    status: str = "candidate"


class RuleCreateRequest(BaseModel):
    organisation_id: uuid.UUID
    rule_code: str
    rule_name: str
    rule_type: str
    tolerance_json: dict[str, Any] = Field(default_factory=dict)
    materiality_json: dict[str, Any] = Field(default_factory=dict)
    timing_window_json: dict[str, Any] = Field(default_factory=dict)
    classification_behavior_json: dict[str, Any] = Field(default_factory=dict)
    effective_from: date
    supersedes_id: uuid.UUID | None = None
    status: str = "candidate"


class RunCreateRequest(BaseModel):
    organisation_id: uuid.UUID
    payroll_run_id: uuid.UUID
    gl_run_id: uuid.UUID
    reporting_period: date


class RunCreateResponse(BaseModel):
    run_id: uuid.UUID
    reconciliation_session_id: uuid.UUID
    run_token: str
    status: str
    idempotent: bool


class RunExecuteResponse(BaseModel):
    run_id: uuid.UUID
    reconciliation_session_id: uuid.UUID
    status: str
    line_count: int
    exception_count: int
    idempotent: bool


class RunSummaryResponse(BaseModel):
    run_id: uuid.UUID
    reconciliation_session_id: uuid.UUID
    line_count: int
    exception_line_count: int
    exception_count: int


class ActionResponse(BaseModel):
    event_id: uuid.UUID | None = None
    exception_id: uuid.UUID | None = None
    evidence_id: uuid.UUID | None = None


class AttachEvidenceRequest(BaseModel):
    evidence_type: str
    evidence_ref: str
    evidence_label: str

