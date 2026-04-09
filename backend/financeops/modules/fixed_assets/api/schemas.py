from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class FaAssetClassCreateRequest(BaseModel):
    entity_id: uuid.UUID
    name: str
    asset_type: str
    default_method: str
    default_useful_life_years: int | None = None
    default_residual_pct: Decimal | None = None
    it_act_block_number: int | None = None
    it_act_depreciation_rate: Decimal | None = None
    coa_asset_account_id: uuid.UUID | None = None
    coa_accum_dep_account_id: uuid.UUID | None = None
    coa_dep_expense_account_id: uuid.UUID | None = None
    is_active: bool = True


class FaAssetClassUpdateRequest(BaseModel):
    name: str | None = None
    asset_type: str | None = None
    default_method: str | None = None
    default_useful_life_years: int | None = None
    default_residual_pct: Decimal | None = None
    it_act_block_number: int | None = None
    it_act_depreciation_rate: Decimal | None = None
    coa_asset_account_id: uuid.UUID | None = None
    coa_accum_dep_account_id: uuid.UUID | None = None
    coa_dep_expense_account_id: uuid.UUID | None = None
    is_active: bool | None = None


class FaAssetClassResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    entity_id: uuid.UUID
    name: str
    asset_type: str
    default_method: str
    default_useful_life_years: int | None = None
    default_residual_pct: Decimal | None = None
    it_act_block_number: int | None = None
    it_act_depreciation_rate: Decimal | None = None
    coa_asset_account_id: uuid.UUID | None = None
    coa_accum_dep_account_id: uuid.UUID | None = None
    coa_dep_expense_account_id: uuid.UUID | None = None
    is_active: bool
    intent_id: uuid.UUID | None = None
    job_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime | None = None


class FaAssetCreateRequest(BaseModel):
    entity_id: uuid.UUID
    asset_class_id: uuid.UUID
    asset_code: str
    asset_name: str
    description: str | None = None
    location: str | None = None
    serial_number: str | None = None
    purchase_date: date
    capitalisation_date: date
    original_cost: Decimal
    residual_value: Decimal = Decimal("0")
    useful_life_years: Decimal
    depreciation_method: str
    it_act_block_number: int | None = None
    status: str = "ACTIVE"
    gaap_overrides: dict[str, object] | None = None
    location_id: uuid.UUID | None = None
    cost_centre_id: uuid.UUID | None = None
    is_active: bool = True


class FaAssetUpdateRequest(BaseModel):
    asset_name: str | None = None
    description: str | None = None
    location: str | None = None
    serial_number: str | None = None
    status: str | None = None
    gaap_overrides: dict[str, object] | None = None
    location_id: uuid.UUID | None = None
    cost_centre_id: uuid.UUID | None = None
    is_active: bool | None = None


class FaAssetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    entity_id: uuid.UUID
    asset_class_id: uuid.UUID
    asset_code: str
    asset_name: str
    description: str | None = None
    location: str | None = None
    serial_number: str | None = None
    purchase_date: date
    capitalisation_date: date
    original_cost: Decimal
    residual_value: Decimal
    useful_life_years: Decimal
    depreciation_method: str
    it_act_block_number: int | None = None
    status: str
    disposal_date: date | None = None
    disposal_proceeds: Decimal | None = None
    gaap_overrides: dict[str, object] | None = None
    location_id: uuid.UUID | None = None
    cost_centre_id: uuid.UUID | None = None
    is_active: bool
    intent_id: uuid.UUID | None = None
    job_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime | None = None


class FaDepreciationRunRequest(BaseModel):
    period_start: date
    period_end: date
    gaap: str = "INDAS"


class FaPeriodDepreciationRequest(BaseModel):
    entity_id: uuid.UUID
    period_start: date
    period_end: date
    gaap: str = "INDAS"


class FaDepreciationRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    entity_id: uuid.UUID
    asset_id: uuid.UUID
    run_date: date
    period_start: date
    period_end: date
    gaap: str
    depreciation_method: str
    opening_nbv: Decimal
    depreciation_amount: Decimal
    closing_nbv: Decimal
    accumulated_dep: Decimal
    run_reference: str
    is_reversal: bool
    intent_id: uuid.UUID | None = None
    job_id: uuid.UUID | None = None
    created_at: datetime


class FaRevaluationRequest(BaseModel):
    fair_value: Decimal
    method: str
    revaluation_date: date


class FaRevaluationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    entity_id: uuid.UUID
    asset_id: uuid.UUID
    revaluation_date: date
    pre_revaluation_cost: Decimal
    pre_revaluation_accum_dep: Decimal
    pre_revaluation_nbv: Decimal
    fair_value: Decimal
    revaluation_surplus: Decimal
    method: str
    intent_id: uuid.UUID | None = None
    job_id: uuid.UUID | None = None
    created_at: datetime


class FaImpairmentRequest(BaseModel):
    value_in_use: Decimal | None = None
    fvlcts: Decimal | None = None
    discount_rate: Decimal | None = None
    impairment_date: date


class FaImpairmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    entity_id: uuid.UUID
    asset_id: uuid.UUID
    impairment_date: date
    pre_impairment_nbv: Decimal
    recoverable_amount: Decimal
    value_in_use: Decimal | None = None
    fvlcts: Decimal | None = None
    impairment_loss: Decimal
    discount_rate: Decimal | None = None
    intent_id: uuid.UUID | None = None
    job_id: uuid.UUID | None = None
    created_at: datetime


class FaDisposalRequest(BaseModel):
    disposal_date: date
    proceeds: Decimal


class FaRegisterLineResponse(BaseModel):
    asset_code: str
    asset_name: str
    class_name: str
    purchase_date: date
    capitalisation_date: date
    original_cost: Decimal
    accumulated_dep: Decimal
    nbv: Decimal
    ytd_depreciation: Decimal
    status: str


class FaRegisterQuery(BaseModel):
    entity_id: uuid.UUID
    as_of_date: date
    gaap: str = Field(default="INDAS")


__all__ = [
    "FaAssetClassCreateRequest",
    "FaAssetClassUpdateRequest",
    "FaAssetClassResponse",
    "FaAssetCreateRequest",
    "FaAssetUpdateRequest",
    "FaAssetResponse",
    "FaDepreciationRunRequest",
    "FaPeriodDepreciationRequest",
    "FaDepreciationRunResponse",
    "FaRevaluationRequest",
    "FaRevaluationResponse",
    "FaImpairmentRequest",
    "FaImpairmentResponse",
    "FaDisposalRequest",
    "FaRegisterLineResponse",
]
