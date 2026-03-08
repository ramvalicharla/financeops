from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from pydantic import BaseModel, Field


class HierarchyNodeIn(BaseModel):
    entity_id: uuid.UUID
    parent_node_temp_key: str | None = None
    node_level: int
    effective_from: date
    effective_to: date | None = None
    supersedes_id: uuid.UUID | None = None
    status: str = "candidate"
    node_key: str


class EntityHierarchyCreateRequest(BaseModel):
    organisation_id: uuid.UUID
    hierarchy_code: str
    hierarchy_name: str
    hierarchy_type: str
    effective_from: date
    effective_to: date | None = None
    supersedes_id: uuid.UUID | None = None
    status: str = "candidate"
    nodes: list[HierarchyNodeIn] = Field(default_factory=list)


class ConsolidationScopeCreateRequest(BaseModel):
    organisation_id: uuid.UUID
    scope_code: str
    scope_name: str
    hierarchy_id: uuid.UUID
    scope_selector_json: dict[str, Any] = Field(default_factory=dict)
    effective_from: date
    effective_to: date | None = None
    supersedes_id: uuid.UUID | None = None
    status: str = "candidate"


class ConsolidationRuleCreateRequest(BaseModel):
    organisation_id: uuid.UUID
    rule_code: str
    rule_name: str
    rule_type: str
    rule_logic_json: dict[str, Any] = Field(default_factory=dict)
    effective_from: date
    effective_to: date | None = None
    supersedes_id: uuid.UUID | None = None
    status: str = "candidate"


class IntercompanyRuleCreateRequest(BaseModel):
    organisation_id: uuid.UUID
    rule_code: str
    source_selector_json: dict[str, Any] = Field(default_factory=dict)
    counterpart_selector_json: dict[str, Any] = Field(default_factory=dict)
    treatment_rule_json: dict[str, Any] = Field(default_factory=dict)
    effective_from: date
    effective_to: date | None = None
    supersedes_id: uuid.UUID | None = None
    status: str = "candidate"


class ConsolidationAdjustmentCreateRequest(BaseModel):
    organisation_id: uuid.UUID
    adjustment_code: str
    adjustment_name: str
    adjustment_type: str
    logic_json: dict[str, Any] = Field(default_factory=dict)
    effective_from: date
    effective_to: date | None = None
    supersedes_id: uuid.UUID | None = None
    status: str = "candidate"


class SourceRunRefIn(BaseModel):
    source_type: str
    run_id: uuid.UUID


class ConsolidationRunCreateRequest(BaseModel):
    organisation_id: uuid.UUID
    reporting_period: date
    source_run_refs: list[SourceRunRefIn]


class ConsolidationRunCreateResponse(BaseModel):
    run_id: uuid.UUID
    run_token: str
    status: str
    idempotent: bool


class ConsolidationRunExecuteResponse(BaseModel):
    run_id: uuid.UUID
    run_token: str
    status: str
    metric_count: int
    variance_count: int
    evidence_count: int
    idempotent: bool

