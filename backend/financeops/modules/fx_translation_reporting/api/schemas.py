from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from pydantic import BaseModel, Field


class ReportingCurrencyCreateRequest(BaseModel):
    organisation_id: uuid.UUID
    reporting_currency_code: str
    reporting_currency_name: str
    reporting_scope_type: str
    reporting_scope_ref: str
    effective_from: date
    effective_to: date | None = None
    supersedes_id: uuid.UUID | None = None
    status: str = "candidate"


class FxTranslationRuleCreateRequest(BaseModel):
    organisation_id: uuid.UUID
    rule_code: str
    rule_name: str
    translation_scope_type: str
    translation_scope_ref: str
    source_currency_selector_json: dict[str, Any] = Field(default_factory=dict)
    target_reporting_currency_code: str
    rule_logic_json: dict[str, Any] = Field(default_factory=dict)
    rate_policy_ref: str
    effective_from: date
    effective_to: date | None = None
    supersedes_id: uuid.UUID | None = None
    status: str = "candidate"


class FxRatePolicyCreateRequest(BaseModel):
    organisation_id: uuid.UUID
    policy_code: str
    policy_name: str
    rate_type: str
    date_selector_logic_json: dict[str, Any] = Field(default_factory=dict)
    fallback_behavior_json: dict[str, Any] = Field(default_factory=dict)
    locked_rate_requirement_flag: bool = True
    source_rate_provider_ref: str = "fx_rate_tables_v1"
    effective_from: date
    effective_to: date | None = None
    supersedes_id: uuid.UUID | None = None
    status: str = "candidate"


class SourceConsolidationRunRefIn(BaseModel):
    source_type: str
    run_id: uuid.UUID


class FxTranslationRunCreateRequest(BaseModel):
    organisation_id: uuid.UUID
    reporting_period: date
    reporting_currency_code: str
    source_consolidation_run_refs: list[SourceConsolidationRunRefIn]


class FxTranslationRunCreateResponse(BaseModel):
    run_id: uuid.UUID
    run_token: str
    status: str
    idempotent: bool


class FxTranslationRunExecuteResponse(BaseModel):
    run_id: uuid.UUID
    run_token: str
    status: str
    metric_count: int
    variance_count: int
    evidence_count: int
    idempotent: bool

