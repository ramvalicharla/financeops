from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from financeops.schemas.accounting_common import DrillResponseBase
from financeops.services.fx.normalization import normalize_currency_code

_MIN_YEAR = 2000
_MAX_YEAR = 2100


class RevenueRateMode(str, Enum):
    daily = "daily"
    month_end_locked = "month_end_locked"


class RevenueRecognitionMethod(str, Enum):
    percentage_of_completion = "percentage_of_completion"
    completed_service = "completed_service"
    milestone_based = "milestone_based"
    straight_line = "straight_line"
    usage_based = "usage_based"


class RevenueObligationInput(BaseModel):
    obligation_code: str = Field(min_length=1, max_length=128)
    description: str = Field(min_length=1, max_length=5000)
    standalone_selling_price: Decimal = Field(gt=Decimal("0"))
    allocation_basis: str = Field(default="ssp", min_length=1, max_length=64)
    recognition_method: RevenueRecognitionMethod


class RevenueLineItemInput(BaseModel):
    line_code: str = Field(min_length=1, max_length=128)
    obligation_code: str | None = Field(default=None, min_length=1, max_length=128)
    line_amount: Decimal = Field(ge=Decimal("0"))
    line_currency: str
    recognition_method: RevenueRecognitionMethod | None = None
    milestone_reference: str | None = Field(default=None, max_length=255)
    usage_reference: str | None = Field(default=None, max_length=255)
    completion_percentage: Decimal | None = Field(default=None, ge=Decimal("0"), le=Decimal("1"))
    completed_flag: bool | None = None
    milestone_achieved: bool | None = None
    usage_quantity: Decimal | None = Field(default=None, ge=Decimal("0"))
    recognition_date: date | None = None
    recognition_start_date: date | None = None
    recognition_end_date: date | None = None

    @field_validator("line_currency", mode="before")
    @classmethod
    def _validate_line_currency(cls, value: Any) -> str:
        return normalize_currency_code(str(value))


class RevenueContractModificationInput(BaseModel):
    effective_date: date
    adjustment_type: str = Field(min_length=1, max_length=64)
    adjustment_reason: str = Field(min_length=1, max_length=5000)
    new_total_contract_value: Decimal | None = Field(default=None, gt=Decimal("0"))
    requires_catch_up: bool = True


class RevenueContractInput(BaseModel):
    contract_number: str = Field(min_length=1, max_length=128)
    customer_id: str = Field(min_length=1, max_length=128)
    contract_currency: str
    contract_start_date: date
    contract_end_date: date
    total_contract_value: Decimal = Field(gt=Decimal("0"))
    source_contract_reference: str = Field(min_length=1, max_length=255)
    policy_code: str = Field(min_length=1, max_length=64)
    policy_version: str = Field(min_length=1, max_length=64)
    performance_obligations: list[RevenueObligationInput] = Field(min_length=1)
    contract_line_items: list[RevenueLineItemInput] = Field(min_length=1)
    modifications: list[RevenueContractModificationInput] = Field(default_factory=list)

    @field_validator("contract_currency", mode="before")
    @classmethod
    def _validate_contract_currency(cls, value: Any) -> str:
        return normalize_currency_code(str(value))

    @model_validator(mode="after")
    def _validate_contract_dates_and_uniqueness(self) -> "RevenueContractInput":
        if self.contract_end_date < self.contract_start_date:
            raise ValueError("contract_end_date must be on or after contract_start_date")

        obligation_codes = [item.obligation_code for item in self.performance_obligations]
        if len(obligation_codes) != len(set(obligation_codes)):
            raise ValueError("performance_obligations contains duplicate obligation_code values")

        line_codes = [item.line_code for item in self.contract_line_items]
        if len(line_codes) != len(set(line_codes)):
            raise ValueError("contract_line_items contains duplicate line_code values")

        valid_obligation_codes = set(obligation_codes)
        for line in self.contract_line_items:
            if line.obligation_code is not None and line.obligation_code not in valid_obligation_codes:
                raise ValueError("line item obligation_code must exist in performance_obligations")

        return self


class RevenueRunRequest(BaseModel):
    reporting_currency: str
    rate_mode: RevenueRateMode = RevenueRateMode.daily
    period_year: int | None = Field(default=None, ge=_MIN_YEAR, le=_MAX_YEAR)
    period_month: int | None = Field(default=None, ge=1, le=12)
    contracts: list[RevenueContractInput] = Field(min_length=1, max_length=200)

    @field_validator("reporting_currency", mode="before")
    @classmethod
    def _validate_reporting_currency(cls, value: Any) -> str:
        return normalize_currency_code(str(value))

    @model_validator(mode="after")
    def _validate_period_fields(self) -> "RevenueRunRequest":
        if self.rate_mode == RevenueRateMode.month_end_locked:
            if self.period_year is None or self.period_month is None:
                raise ValueError("period_year and period_month are required for month_end_locked rate_mode")

        contract_numbers = [contract.contract_number for contract in self.contracts]
        if len(contract_numbers) != len(set(contract_numbers)):
            raise ValueError("contracts contains duplicate contract_number values")
        return self


class RevenueRunAcceptedResponse(BaseModel):
    run_id: str
    workflow_id: str
    status: str
    correlation_id: str


class RevenueRunStatusResponse(BaseModel):
    run_id: str
    status: str
    event_seq: int
    event_time: datetime
    metadata: dict[str, Any] | None = None


class RevenueResultRow(BaseModel):
    schedule_id: str
    contract_id: str
    obligation_id: str
    contract_line_item_id: str
    period_seq: int
    recognition_date: date
    schedule_version_token: str
    recognition_method: str
    recognized_amount_reporting_currency: str
    cumulative_recognized_reporting_currency: str


class RevenueResultsResponse(BaseModel):
    run_id: str
    reporting_currency: str
    rows: list[RevenueResultRow]
    count: int
    total_recognized_reporting_currency: str


class RevenueContractDrillResponse(DrillResponseBase):
    contract_number: str
    customer_id: str
    contract_currency: str
    total_contract_value: str


class RevenueObligationDrillResponse(DrillResponseBase):
    contract_id: UUID
    obligation_code: str
    recognition_method: str
    standalone_selling_price: str


class RevenueScheduleDrillResponse(DrillResponseBase):
    contract_id: UUID
    obligation_id: UUID
    contract_line_item_id: UUID
    period_seq: int
    recognition_date: date
    schedule_version_token: str
    recognition_method: str
    recognized_amount_reporting_currency: str
    cumulative_recognized_reporting_currency: str


class RevenueJournalDrillResponse(DrillResponseBase):
    schedule_id: UUID
    journal_reference: str
    entry_date: date
    debit_account: str
    credit_account: str
    amount_reporting_currency: str
