from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from financeops.schemas.accounting_common import DrillResponseBase
from financeops.services.accounting_common.quantization_policy import quantize_persisted_amount
from financeops.services.fx.normalization import normalize_currency_code

_MIN_YEAR = 2000
_MAX_YEAR = 2100


class PrepaidPatternType(str, Enum):
    straight_line = "straight_line"
    weighted_period = "weighted_period"
    explicit_percentages = "explicit_percentages"
    explicit_amounts = "explicit_amounts"


class PrepaidRateMode(str, Enum):
    month_end_locked = "month_end_locked"
    daily_selected = "daily_selected"


class PrepaidPatternPeriodInput(BaseModel):
    period_seq: int = Field(ge=1, le=1200)
    period_start_date: date
    period_end_date: date
    recognition_date: date
    weight: Decimal | None = Field(default=None, gt=Decimal("0"))
    percentage: Decimal | None = Field(default=None, ge=Decimal("0"))
    amount: Decimal | None = Field(default=None, ge=Decimal("0"))

    @model_validator(mode="after")
    def _validate_dates(self) -> "PrepaidPatternPeriodInput":
        if self.period_end_date < self.period_start_date:
            raise ValueError("period_end_date must be on or after period_start_date")
        if not (self.period_start_date <= self.recognition_date <= self.period_end_date):
            raise ValueError("recognition_date must fall within the period range")
        return self


class PrepaidAdjustmentInput(BaseModel):
    effective_date: date
    adjustment_type: str = Field(min_length=1, max_length=64)
    adjustment_reason: str = Field(min_length=1, max_length=5000)
    idempotency_key: str = Field(min_length=1, max_length=128)
    catch_up_amount_reporting_currency: Decimal = Field(default=Decimal("0"))

    @field_validator("catch_up_amount_reporting_currency", mode="before")
    @classmethod
    def _quantize_catch_up(cls, value: Any) -> Decimal:
        return quantize_persisted_amount(value)


class PrepaidInput(BaseModel):
    prepaid_code: str = Field(min_length=1, max_length=128)
    description: str = Field(min_length=1, max_length=5000)
    prepaid_currency: str
    reporting_currency: str
    term_start_date: date
    term_end_date: date
    base_amount_contract_currency: Decimal = Field(gt=Decimal("0"))
    period_frequency: str = Field(default="monthly", min_length=1, max_length=16)
    pattern_type: PrepaidPatternType
    periods: list[PrepaidPatternPeriodInput] | None = None
    rate_mode: PrepaidRateMode = PrepaidRateMode.month_end_locked
    source_expense_reference: str = Field(min_length=1, max_length=255)
    parent_reference_id: UUID | None = None
    source_reference_id: UUID | None = None
    adjustments: list[PrepaidAdjustmentInput] = Field(default_factory=list)

    @field_validator("prepaid_currency", "reporting_currency", mode="before")
    @classmethod
    def _validate_currency(cls, value: Any) -> str:
        return normalize_currency_code(str(value))

    @field_validator("base_amount_contract_currency", mode="before")
    @classmethod
    def _quantize_base_amount(cls, value: Any) -> Decimal:
        return quantize_persisted_amount(value)

    @model_validator(mode="after")
    def _validate_shape(self) -> "PrepaidInput":
        if self.term_end_date < self.term_start_date:
            raise ValueError("term_end_date must be on or after term_start_date")
        if self.period_frequency.lower() != "monthly":
            raise ValueError("period_frequency must be monthly")

        periods = self.periods or []
        if self.pattern_type == PrepaidPatternType.straight_line and periods:
            raise ValueError("periods must be omitted for straight_line pattern")
        if self.pattern_type != PrepaidPatternType.straight_line and not periods:
            raise ValueError("periods are required for non-straight_line patterns")

        if periods:
            sequences = [period.period_seq for period in periods]
            if len(sequences) != len(set(sequences)):
                raise ValueError("period_seq must be unique")
        return self


class PrepaidRunRequest(BaseModel):
    period_year: int | None = Field(default=None, ge=_MIN_YEAR, le=_MAX_YEAR)
    period_month: int | None = Field(default=None, ge=1, le=12)
    prepaids: list[PrepaidInput] = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def _validate_unique_prepaid_codes(self) -> "PrepaidRunRequest":
        codes = [item.prepaid_code for item in self.prepaids]
        if len(codes) != len(set(codes)):
            raise ValueError("prepaids contains duplicate prepaid_code values")
        return self


class PrepaidRunAcceptedResponse(BaseModel):
    run_id: str
    workflow_id: str
    status: str
    correlation_id: str
    intent_id: str | None = None
    job_id: str | None = None


class PrepaidRunStatusResponse(BaseModel):
    run_id: str
    status: str
    event_seq: int
    event_time: datetime
    metadata: dict[str, Any] | None = None


class PrepaidResultRow(BaseModel):
    schedule_id: str
    prepaid_id: str
    period_seq: int
    amortization_date: date
    schedule_version_token: str
    amortized_amount_reporting_currency: str
    cumulative_amortized_reporting_currency: str
    fx_rate_used: str
    fx_rate_date: date
    fx_rate_source: str


class PrepaidResultsResponse(BaseModel):
    run_id: str
    rows: list[PrepaidResultRow]
    count: int
    total_amortized_reporting_currency: str


class PrepaidRegistryDrillResponse(DrillResponseBase):
    prepaid_code: str
    prepaid_currency: str
    reporting_currency: str
    base_amount_contract_currency: str
    pattern_type: str
    rate_mode: str


class PrepaidScheduleDrillResponse(DrillResponseBase):
    prepaid_id: UUID
    period_seq: int
    amortization_date: date
    schedule_version_token: str
    amortized_amount_reporting_currency: str
    cumulative_amortized_reporting_currency: str
    fx_rate_used: str
    fx_rate_date: date
    fx_rate_source: str


class PrepaidJournalDrillResponse(DrillResponseBase):
    prepaid_id: UUID
    schedule_id: UUID
    journal_reference: str
    entry_date: date
    debit_account: str
    credit_account: str
    amount_reporting_currency: str
