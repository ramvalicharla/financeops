from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class StatementDefinitionCreateRequest(BaseModel):
    organisation_id: uuid.UUID
    statement_code: str = Field(min_length=1, max_length=128)
    statement_name: str = Field(min_length=1, max_length=255)
    reporting_currency_basis: str = Field(pattern="^(source_currency|reporting_currency)$")
    ownership_basis_flag: bool = False
    effective_from: date
    effective_to: date | None = None
    supersedes_id: uuid.UUID | None = None
    status: str = Field(default="candidate", pattern="^(candidate|active|superseded|rejected)$")


class RuleCreateRequest(BaseModel):
    organisation_id: uuid.UUID
    rule_code: str = Field(min_length=1, max_length=128)
    rule_name: str = Field(min_length=1, max_length=255)
    rule_type: str = Field(
        pattern="^(opening_balance_rule|retained_earnings_bridge_rule|oci_accumulation_rule|cta_derivation_rule|ownership_attribution_rule|minority_interest_equity_rule|closing_balance_rule)$"
    )
    source_selector_json: dict[str, Any] = Field(default_factory=dict)
    derivation_logic_json: dict[str, Any] = Field(default_factory=dict)
    fx_interaction_logic_json_nullable: dict[str, Any] | None = None
    ownership_interaction_logic_json_nullable: dict[str, Any] | None = None
    effective_from: date
    effective_to: date | None = None
    supersedes_id: uuid.UUID | None = None
    status: str = Field(default="candidate", pattern="^(candidate|active|superseded|rejected)$")


class EquityRunCreateRequest(BaseModel):
    organisation_id: uuid.UUID
    reporting_period: date
    consolidation_run_ref_nullable: uuid.UUID | None = None
    fx_translation_run_ref_nullable: uuid.UUID | None = None
    ownership_consolidation_run_ref_nullable: uuid.UUID | None = None


class EquityRunCreateResponse(BaseModel):
    run_id: uuid.UUID
    run_token: str
    status: str
    idempotent: bool


class EquityRunExecuteResponse(BaseModel):
    run_id: uuid.UUID
    run_token: str
    status: str
    line_count: int
    evidence_count: int
    idempotent: bool


class LineDefinitionCreateRequest(BaseModel):
    organisation_id: uuid.UUID
    statement_definition_id: uuid.UUID
    line_code: str = Field(min_length=1, max_length=128)
    line_name: str = Field(min_length=1, max_length=255)
    line_type: str = Field(
        pattern="^(share_capital|share_premium|retained_earnings|other_reserves|oci_accumulated|cta_reserve|minority_interest|total_equity)$"
    )
    presentation_order: int = Field(ge=1)
    rollforward_required_flag: bool = True
    effective_from: date
    effective_to: date | None = None
    supersedes_id: uuid.UUID | None = None
    status: str = Field(default="candidate", pattern="^(candidate|active|superseded|rejected)$")


class SourceMappingCreateRequest(BaseModel):
    organisation_id: uuid.UUID
    mapping_code: str = Field(min_length=1, max_length=128)
    line_code: str = Field(min_length=1, max_length=128)
    source_type: str = Field(pattern="^(consolidation_result|fx_translation_result|ownership_result|pnl_result|adjustment_ref)$")
    source_selector_json: dict[str, Any] = Field(default_factory=dict)
    transformation_logic_json: dict[str, Any] = Field(default_factory=dict)
    effective_from: date
    effective_to: date | None = None
    supersedes_id: uuid.UUID | None = None
    status: str = Field(default="candidate", pattern="^(candidate|active|superseded|rejected)$")


class DecimalLineResponse(BaseModel):
    id: uuid.UUID
    line_no: int
    line_code: str
    opening_balance: Decimal
    movement_amount: Decimal
    closing_balance: Decimal
