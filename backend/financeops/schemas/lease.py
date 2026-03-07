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


class LeaseRateMode(str, Enum):
    daily = "daily"
    month_end_locked = "month_end_locked"


class LeasePaymentFrequency(str, Enum):
    monthly = "monthly"
    quarterly = "quarterly"
    annual = "annual"
    custom = "custom"


class LeasePaymentInput(BaseModel):
    payment_date: date
    payment_amount_lease_currency: Decimal = Field(ge=Decimal("0"))
    payment_type: str = Field(min_length=1, max_length=64)
    payment_sequence: int = Field(ge=1, le=10000)


class LeaseImpairmentInput(BaseModel):
    schedule_date: date
    impairment_amount_reporting_currency: Decimal = Field(ge=Decimal("0"))


class LeaseModificationInput(BaseModel):
    effective_date: date
    modification_type: str = Field(min_length=1, max_length=64)
    modification_reason: str = Field(min_length=1, max_length=5000)
    new_discount_rate: Decimal | None = Field(default=None, gt=Decimal("0"))
    new_end_date: date | None = None
    remeasurement_delta_reporting_currency: Decimal | None = None


class LeaseInput(BaseModel):
    lease_number: str = Field(min_length=1, max_length=128)
    counterparty_id: str = Field(min_length=1, max_length=128)
    lease_currency: str
    commencement_date: date
    end_date: date
    payment_frequency: LeasePaymentFrequency
    initial_discount_rate: Decimal = Field(gt=Decimal("0"), le=Decimal("1"))
    discount_rate_source: str = Field(min_length=1, max_length=64)
    discount_rate_reference_date: date
    discount_rate_policy_code: str = Field(min_length=1, max_length=64)
    initial_measurement_basis: str = Field(default="present_value", min_length=1, max_length=64)
    source_lease_reference: str = Field(min_length=1, max_length=255)
    policy_code: str = Field(min_length=1, max_length=64)
    policy_version: str = Field(min_length=1, max_length=64)
    payments: list[LeasePaymentInput] = Field(min_length=1)
    modifications: list[LeaseModificationInput] = Field(default_factory=list)
    impairments: list[LeaseImpairmentInput] = Field(default_factory=list)

    @field_validator("lease_currency", mode="before")
    @classmethod
    def _validate_lease_currency(cls, value: Any) -> str:
        return normalize_currency_code(str(value))

    @model_validator(mode="after")
    def _validate_dates_and_sequences(self) -> "LeaseInput":
        if self.end_date < self.commencement_date:
            raise ValueError("end_date must be on or after commencement_date")

        sequences = [item.payment_sequence for item in self.payments]
        if len(sequences) != len(set(sequences)):
            raise ValueError("payments contains duplicate payment_sequence values")

        ordered_by_sequence = sorted(self.payments, key=lambda item: item.payment_sequence)
        for idx in range(1, len(ordered_by_sequence)):
            previous = ordered_by_sequence[idx - 1]
            current = ordered_by_sequence[idx]
            if current.payment_date < previous.payment_date:
                raise ValueError("payments must not regress in payment_date when ordered by payment_sequence")

        for modification in self.modifications:
            if modification.new_end_date is not None and modification.new_end_date < self.commencement_date:
                raise ValueError("modification new_end_date must be on or after commencement_date")
        return self


class LeaseRunRequest(BaseModel):
    reporting_currency: str
    rate_mode: LeaseRateMode = LeaseRateMode.daily
    period_year: int | None = Field(default=None, ge=_MIN_YEAR, le=_MAX_YEAR)
    period_month: int | None = Field(default=None, ge=1, le=12)
    leases: list[LeaseInput] = Field(min_length=1, max_length=200)

    @field_validator("reporting_currency", mode="before")
    @classmethod
    def _validate_reporting_currency(cls, value: Any) -> str:
        return normalize_currency_code(str(value))

    @model_validator(mode="after")
    def _validate_period_and_uniqueness(self) -> "LeaseRunRequest":
        if self.rate_mode == LeaseRateMode.month_end_locked:
            if self.period_year is None or self.period_month is None:
                raise ValueError("period_year and period_month are required for month_end_locked rate_mode")

        lease_numbers = [lease.lease_number for lease in self.leases]
        if len(lease_numbers) != len(set(lease_numbers)):
            raise ValueError("leases contains duplicate lease_number values")
        return self


class LeaseRunAcceptedResponse(BaseModel):
    run_id: str
    workflow_id: str
    status: str
    correlation_id: str


class LeaseRunStatusResponse(BaseModel):
    run_id: str
    status: str
    event_seq: int
    event_time: datetime
    metadata: dict[str, Any] | None = None


class LeaseLiabilityResultRow(BaseModel):
    line_id: str
    lease_id: str
    period_seq: int
    schedule_date: date
    schedule_version_token: str
    opening_liability_reporting_currency: str
    interest_expense_reporting_currency: str
    payment_amount_reporting_currency: str
    closing_liability_reporting_currency: str


class LeaseRouResultRow(BaseModel):
    line_id: str
    lease_id: str
    period_seq: int
    schedule_date: date
    schedule_version_token: str
    opening_rou_reporting_currency: str
    amortization_expense_reporting_currency: str
    impairment_amount_reporting_currency: str
    closing_rou_reporting_currency: str


class LeaseResultsResponse(BaseModel):
    run_id: str
    reporting_currency: str
    liability_rows: list[LeaseLiabilityResultRow]
    rou_rows: list[LeaseRouResultRow]
    liability_count: int
    rou_count: int
    total_interest_reporting_currency: str
    total_amortization_reporting_currency: str


class LeaseContractDrillResponse(DrillResponseBase):
    lease_number: str
    lease_currency: str
    initial_discount_rate: str
    payment_frequency: str


class LeasePaymentDrillResponse(DrillResponseBase):
    lease_id: UUID
    payment_date: date
    payment_amount_lease_currency: str
    payment_type: str
    payment_sequence: int


class LeaseLiabilityDrillResponse(DrillResponseBase):
    lease_id: UUID
    payment_id: UUID | None
    period_seq: int
    schedule_date: date
    schedule_version_token: str
    opening_liability_reporting_currency: str
    interest_expense_reporting_currency: str
    payment_amount_reporting_currency: str
    closing_liability_reporting_currency: str


class LeaseRouDrillResponse(DrillResponseBase):
    lease_id: UUID
    period_seq: int
    schedule_date: date
    schedule_version_token: str
    opening_rou_reporting_currency: str
    amortization_expense_reporting_currency: str
    impairment_amount_reporting_currency: str
    closing_rou_reporting_currency: str


class LeaseJournalDrillResponse(DrillResponseBase):
    lease_id: UUID
    liability_schedule_id: UUID | None
    rou_schedule_id: UUID | None
    journal_reference: str
    entry_date: date
    debit_account: str
    credit_account: str
    amount_reporting_currency: str
