from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class OwnershipStructureCreateRequest(BaseModel):
    organisation_id: uuid.UUID
    ownership_structure_code: str
    ownership_structure_name: str
    hierarchy_scope_ref: str
    ownership_basis_type: str
    effective_from: date
    effective_to: date | None = None
    supersedes_id: uuid.UUID | None = None
    status: str = "candidate"


class OwnershipRelationshipCreateRequest(BaseModel):
    organisation_id: uuid.UUID
    ownership_structure_id: uuid.UUID
    parent_entity_id: uuid.UUID
    child_entity_id: uuid.UUID
    ownership_percentage: Decimal
    voting_percentage_nullable: Decimal | None = None
    control_indicator: bool = False
    minority_interest_indicator: bool = False
    proportionate_consolidation_indicator: bool = False
    effective_from: date
    effective_to: date | None = None
    supersedes_id: uuid.UUID | None = None
    status: str = "candidate"


class OwnershipRuleCreateRequest(BaseModel):
    organisation_id: uuid.UUID
    rule_code: str
    rule_name: str
    rule_type: str
    rule_logic_json: dict[str, Any] = Field(default_factory=dict)
    attribution_policy_json: dict[str, Any] = Field(default_factory=dict)
    effective_from: date
    effective_to: date | None = None
    supersedes_id: uuid.UUID | None = None
    status: str = "candidate"


class MinorityInterestRuleCreateRequest(BaseModel):
    organisation_id: uuid.UUID
    rule_code: str
    rule_name: str
    attribution_basis_type: str
    calculation_logic_json: dict[str, Any] = Field(default_factory=dict)
    presentation_logic_json: dict[str, Any] = Field(default_factory=dict)
    effective_from: date
    effective_to: date | None = None
    supersedes_id: uuid.UUID | None = None
    status: str = "candidate"


class SourceConsolidationRunRefIn(BaseModel):
    source_type: str
    run_id: uuid.UUID


class OwnershipRunCreateRequest(BaseModel):
    organisation_id: uuid.UUID
    reporting_period: date
    source_consolidation_run_refs: list[SourceConsolidationRunRefIn]
    fx_translation_run_ref_nullable: uuid.UUID | None = None


class OwnershipRunCreateResponse(BaseModel):
    run_id: uuid.UUID
    run_token: str
    status: str
    idempotent: bool


class OwnershipRunExecuteResponse(BaseModel):
    run_id: uuid.UUID
    run_token: str
    status: str
    metric_count: int
    variance_count: int
    evidence_count: int
    idempotent: bool
