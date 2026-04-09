from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from financeops.schemas.accounting_common import DrillResponseBase
from financeops.services.accounting_common.quantization_policy import quantize_persisted_amount, quantize_rate
from financeops.services.fx.normalization import normalize_currency_code

_MIN_YEAR = 2000
_MAX_YEAR = 2100


class FarDepreciationMethod(str, Enum):
    straight_line = "straight_line"
    reducing_balance = "reducing_balance"
    non_depreciable = "non_depreciable"


class FarRateMode(str, Enum):
    month_end_locked = "month_end_locked"
    daily_selected = "daily_selected"


class AssetImpairmentInput(BaseModel):
    impairment_date: date
    impairment_amount_reporting_currency: Decimal = Field(gt=Decimal("0"))
    idempotency_key: str = Field(min_length=1, max_length=128)
    reason: str = Field(min_length=1, max_length=2000)

    @field_validator("impairment_amount_reporting_currency", mode="before")
    @classmethod
    def _quantize_amount(cls, value: Any) -> Decimal:
        return quantize_persisted_amount(value)


class AssetDisposalInput(BaseModel):
    disposal_date: date
    proceeds_reporting_currency: Decimal
    disposal_cost_reporting_currency: Decimal = Decimal("0")
    idempotency_key: str = Field(min_length=1, max_length=128)

    @field_validator("proceeds_reporting_currency", "disposal_cost_reporting_currency", mode="before")
    @classmethod
    def _quantize_amount(cls, value: Any) -> Decimal:
        return quantize_persisted_amount(value)


class FixedAssetInput(BaseModel):
    asset_code: str = Field(min_length=1, max_length=128)
    description: str = Field(min_length=1, max_length=5000)
    entity_id: str = Field(min_length=1, max_length=128)
    asset_class: str = Field(min_length=1, max_length=64)
    asset_currency: str
    reporting_currency: str
    capitalization_date: date
    in_service_date: date
    capitalized_amount_asset_currency: Decimal = Field(gt=Decimal("0"))
    depreciation_method: FarDepreciationMethod
    useful_life_months: int | None = Field(default=None, ge=1, le=1200)
    reducing_balance_rate_annual: Decimal | None = Field(default=None, gt=Decimal("0"), le=Decimal("1"))
    residual_value_reporting_currency: Decimal = Field(ge=Decimal("0"))
    rate_mode: FarRateMode = FarRateMode.month_end_locked
    source_acquisition_reference: str = Field(min_length=1, max_length=255)
    parent_reference_id: UUID | None = None
    source_reference_id: UUID | None = None
    impairments: list[AssetImpairmentInput] = Field(default_factory=list)
    disposals: list[AssetDisposalInput] = Field(default_factory=list)

    @field_validator("asset_currency", "reporting_currency", mode="before")
    @classmethod
    def _normalize_currency(cls, value: Any) -> str:
        return normalize_currency_code(str(value))

    @field_validator(
        "capitalized_amount_asset_currency",
        "reducing_balance_rate_annual",
        "residual_value_reporting_currency",
        mode="before",
    )
    @classmethod
    def _quantize_numbers(cls, value: Any) -> Decimal | None:
        if value is None:
            return None
        return quantize_persisted_amount(value)

    @model_validator(mode="after")
    def _validate_shape(self) -> "FixedAssetInput":
        if self.in_service_date < self.capitalization_date:
            raise ValueError("in_service_date must be on or after capitalization_date")

        if self.depreciation_method == FarDepreciationMethod.straight_line:
            if self.useful_life_months is None:
                raise ValueError("useful_life_months is required for straight_line")
            if self.reducing_balance_rate_annual is not None:
                raise ValueError("reducing_balance_rate_annual must be null for straight_line")

        if self.depreciation_method == FarDepreciationMethod.reducing_balance:
            if self.reducing_balance_rate_annual is None:
                raise ValueError("reducing_balance_rate_annual is required for reducing_balance")

        if self.depreciation_method == FarDepreciationMethod.non_depreciable:
            if self.useful_life_months is not None or self.reducing_balance_rate_annual is not None:
                raise ValueError("non_depreciable assets cannot carry depreciation method parameters")

        seen_impairment = set()
        for impairment in self.impairments:
            key = (impairment.impairment_date, impairment.idempotency_key)
            if key in seen_impairment:
                raise ValueError("duplicate impairment idempotency in asset payload")
            seen_impairment.add(key)

        seen_disposal = set()
        for disposal in self.disposals:
            key = (disposal.disposal_date, disposal.idempotency_key)
            if key in seen_disposal:
                raise ValueError("duplicate disposal idempotency in asset payload")
            seen_disposal.add(key)

        return self


class FarRunRequest(BaseModel):
    period_year: int | None = Field(default=None, ge=_MIN_YEAR, le=_MAX_YEAR)
    period_month: int | None = Field(default=None, ge=1, le=12)
    assets: list[FixedAssetInput] = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def _validate_unique_asset_codes(self) -> "FarRunRequest":
        codes = [item.asset_code for item in self.assets]
        if len(codes) != len(set(codes)):
            raise ValueError("assets contains duplicate asset_code values")
        return self


class FarRunAcceptedResponse(BaseModel):
    run_id: str
    workflow_id: str
    status: str
    correlation_id: str
    intent_id: str | None = None
    job_id: str | None = None


class FarRunStatusResponse(BaseModel):
    run_id: str
    status: str
    event_seq: int
    event_time: datetime
    metadata: dict[str, Any] | None = None


class FarResultRow(BaseModel):
    schedule_id: str
    asset_id: str
    period_seq: int
    depreciation_date: date
    schedule_version_token: str
    opening_carrying_amount_reporting_currency: str
    depreciation_amount_reporting_currency: str
    closing_carrying_amount_reporting_currency: str
    fx_rate_used: str
    fx_rate_date: date
    fx_rate_source: str


class FarResultsResponse(BaseModel):
    run_id: str
    rows: list[FarResultRow]
    count: int
    total_depreciation_reporting_currency: str


class FixedAssetDrillResponse(DrillResponseBase):
    asset_code: str
    depreciation_method: str
    useful_life_months: int | None
    reducing_balance_rate_annual: str | None
    residual_value_reporting_currency: str


class FarDepreciationDrillResponse(DrillResponseBase):
    asset_id: UUID
    period_seq: int
    depreciation_date: date
    schedule_version_token: str
    opening_carrying_amount_reporting_currency: str
    depreciation_amount_reporting_currency: str
    closing_carrying_amount_reporting_currency: str
    fx_rate_used: str
    fx_rate_date: date
    fx_rate_source: str


class FarImpairmentDrillResponse(DrillResponseBase):
    asset_id: UUID
    impairment_date: date
    impairment_amount_reporting_currency: str
    prior_schedule_version_token: str
    new_schedule_version_token: str


class FarDisposalDrillResponse(DrillResponseBase):
    asset_id: UUID
    disposal_date: date
    proceeds_reporting_currency: str
    disposal_cost_reporting_currency: str
    carrying_amount_reporting_currency: str
    gain_loss_reporting_currency: str
    prior_schedule_version_token: str
    new_schedule_version_token: str


class FarJournalDrillResponse(DrillResponseBase):
    asset_id: UUID
    depreciation_schedule_id: UUID | None
    impairment_id: UUID | None
    disposal_id: UUID | None
    journal_reference: str
    line_seq: int
    entry_date: date
    debit_account: str
    credit_account: str
    amount_reporting_currency: str


def decimal_text(value: Decimal) -> str:
    return f"{quantize_persisted_amount(value):.6f}"


def rate_text(value: Decimal) -> str:
    return f"{quantize_rate(value):.6f}"
