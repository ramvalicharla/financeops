from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from pydantic import BaseModel, Field


class BoardPackDefinitionCreateRequest(BaseModel):
    organisation_id: uuid.UUID
    board_pack_code: str
    board_pack_name: str
    audience_scope: str = "board"
    section_order_json: dict[str, Any] = Field(default_factory=dict)
    inclusion_config_json: dict[str, Any] = Field(default_factory=dict)
    effective_from: date
    effective_to: date | None = None
    supersedes_id: uuid.UUID | None = None
    status: str = "candidate"


class BoardPackSectionCreateRequest(BaseModel):
    organisation_id: uuid.UUID
    section_code: str
    section_name: str
    section_type: str
    render_logic_json: dict[str, Any] = Field(default_factory=dict)
    section_order_default: int
    narrative_template_ref: str | None = None
    risk_inclusion_rule_json: dict[str, Any] = Field(default_factory=dict)
    anomaly_inclusion_rule_json: dict[str, Any] = Field(default_factory=dict)
    metric_inclusion_rule_json: dict[str, Any] = Field(default_factory=dict)
    effective_from: date
    effective_to: date | None = None
    supersedes_id: uuid.UUID | None = None
    status: str = "candidate"


class NarrativeTemplateCreateRequest(BaseModel):
    organisation_id: uuid.UUID
    template_code: str
    template_name: str
    template_type: str
    template_text: str
    template_body_json: dict[str, Any] = Field(default_factory=dict)
    placeholder_schema_json: dict[str, Any] = Field(default_factory=dict)
    effective_from: date
    effective_to: date | None = None
    supersedes_id: uuid.UUID | None = None
    status: str = "candidate"


class InclusionRuleCreateRequest(BaseModel):
    organisation_id: uuid.UUID
    rule_code: str
    rule_name: str
    rule_type: str
    inclusion_logic_json: dict[str, Any] = Field(default_factory=dict)
    effective_from: date
    effective_to: date | None = None
    supersedes_id: uuid.UUID | None = None
    status: str = "candidate"


class BoardPackRunCreateRequest(BaseModel):
    organisation_id: uuid.UUID
    reporting_period: date
    source_metric_run_ids: list[uuid.UUID]
    source_risk_run_ids: list[uuid.UUID]
    source_anomaly_run_ids: list[uuid.UUID]


class BoardPackRunCreateResponse(BaseModel):
    run_id: uuid.UUID
    run_token: str
    status: str
    idempotent: bool
    intent_id: uuid.UUID | None = None
    job_id: uuid.UUID | None = None
    determinism_hash: str | None = None
    snapshot_refs: list[str] = Field(default_factory=list)


class BoardPackRunExecuteResponse(BaseModel):
    run_id: uuid.UUID
    run_token: str
    status: str
    section_count: int
    narrative_count: int
    evidence_count: int
    idempotent: bool
    intent_id: uuid.UUID | None = None
    job_id: uuid.UUID | None = None
    determinism_hash: str | None = None
    snapshot_refs: list[str] = Field(default_factory=list)
