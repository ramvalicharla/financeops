from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class StatementDefinitionCreateRequest(BaseModel):
    organisation_id: uuid.UUID
    definition_code: str
    definition_name: str
    method_type: str
    layout_json: dict[str, Any] = Field(default_factory=dict)
    effective_from: date
    effective_to: date | None = None
    supersedes_id: uuid.UUID | None = None
    status: str = "candidate"


class LineMappingCreateRequest(BaseModel):
    organisation_id: uuid.UUID
    mapping_code: str
    line_code: str
    line_name: str
    section_code: str
    line_order: int
    method_type: str
    source_metric_code: str
    sign_multiplier: Decimal = Decimal("1.000000")
    aggregation_type: str = "sum"
    ownership_applicability: str = "any"
    fx_applicability: str = "any"
    effective_from: date
    effective_to: date | None = None
    supersedes_id: uuid.UUID | None = None
    status: str = "candidate"


class BridgeRuleCreateRequest(BaseModel):
    organisation_id: uuid.UUID
    rule_code: str
    rule_name: str
    bridge_logic_json: dict[str, Any] = Field(default_factory=dict)
    ownership_logic_json: dict[str, Any] = Field(default_factory=dict)
    fx_logic_json: dict[str, Any] = Field(default_factory=dict)
    effective_from: date
    effective_to: date | None = None
    supersedes_id: uuid.UUID | None = None
    status: str = "candidate"


class CashFlowRunCreateRequest(BaseModel):
    organisation_id: uuid.UUID
    reporting_period: date
    source_consolidation_run_ref: uuid.UUID
    source_fx_translation_run_ref_nullable: uuid.UUID | None = None
    source_ownership_consolidation_run_ref_nullable: uuid.UUID | None = None


class CashFlowRunCreateResponse(BaseModel):
    run_id: uuid.UUID
    run_token: str
    status: str
    idempotent: bool


class CashFlowRunExecuteResponse(BaseModel):
    run_id: uuid.UUID
    run_token: str
    status: str
    line_count: int
    evidence_count: int
    idempotent: bool
