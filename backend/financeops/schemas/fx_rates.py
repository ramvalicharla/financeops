from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from financeops.services.fx.normalization import (
    normalize_currency_code,
    normalize_currency_pair,
    normalize_rate_decimal,
)

_MIN_SUPPORTED_YEAR = 2000
_MAX_SUPPORTED_YEAR = 2100


class FetchLiveRatesRequest(BaseModel):
    base_currency: str
    quote_currency: str
    rate_date: date | None = None

    @field_validator("base_currency", "quote_currency", mode="before")
    @classmethod
    def _validate_currency(cls, value: Any) -> str:
        return normalize_currency_code(str(value))

    @model_validator(mode="after")
    def _validate_pair(self) -> "FetchLiveRatesRequest":
        base, quote = normalize_currency_pair(self.base_currency, self.quote_currency)
        if base == quote:
            raise ValueError("base_currency and quote_currency must differ")
        self.base_currency = base
        self.quote_currency = quote
        return self


class ProviderComparisonRow(BaseModel):
    provider: str
    status: str
    rate: str | None = None
    rate_date: str | None = None
    error: str | None = None


class FetchLiveRatesResponse(BaseModel):
    fetch_run_id: str
    status: str
    base_currency: str
    quote_currency: str
    rate_date: str
    selected_rate: str | None
    selected_source: str | None
    selection_method: str | None
    fallback_used: bool
    providers: list[ProviderComparisonRow]


class CompareRatesResponse(BaseModel):
    comparison: FetchLiveRatesResponse | None


class ManualMonthlyRateCreateRequest(BaseModel):
    period_year: int = Field(ge=_MIN_SUPPORTED_YEAR, le=_MAX_SUPPORTED_YEAR)
    period_month: int = Field(ge=1, le=12)
    base_currency: str
    quote_currency: str
    rate: Decimal
    reason: str = Field(min_length=3, max_length=1000)
    supersedes_rate_id: UUID | None = None

    @field_validator("base_currency", "quote_currency", mode="before")
    @classmethod
    def _validate_currency(cls, value: Any) -> str:
        return normalize_currency_code(str(value))

    @field_validator("rate")
    @classmethod
    def _validate_rate(cls, value: Decimal) -> Decimal:
        return normalize_rate_decimal(value)

    @model_validator(mode="after")
    def _validate_pair(self) -> "ManualMonthlyRateCreateRequest":
        base, quote = normalize_currency_pair(self.base_currency, self.quote_currency)
        if base == quote:
            raise ValueError("base_currency and quote_currency must differ")
        self.base_currency = base
        self.quote_currency = quote
        return self


class ManualMonthlyRateRecord(BaseModel):
    rate_id: str
    period_year: int
    period_month: int
    base_currency: str
    quote_currency: str
    rate: str
    reason: str
    supersedes_rate_id: str | None
    source_type: str
    is_month_end_locked: bool
    created_at: str


class ManualMonthlyRateListResponse(BaseModel):
    rates: list[ManualMonthlyRateRecord]
    count: int


class ConvertDailyLineRequest(BaseModel):
    reference: str | None = None
    transaction_date: date
    amount: Decimal
    base_currency: str
    quote_currency: str

    @field_validator("base_currency", "quote_currency", mode="before")
    @classmethod
    def _validate_currency(cls, value: Any) -> str:
        return normalize_currency_code(str(value))

    @model_validator(mode="after")
    def _validate_pair(self) -> "ConvertDailyLineRequest":
        base, quote = normalize_currency_pair(self.base_currency, self.quote_currency)
        if base == quote:
            raise ValueError("base_currency and quote_currency must differ")
        self.base_currency = base
        self.quote_currency = quote
        return self


class ConvertDailyRequest(BaseModel):
    lines: list[ConvertDailyLineRequest] = Field(min_length=1, max_length=1000)


class ConvertDailyLineResponse(BaseModel):
    reference: str | None
    transaction_date: str
    amount: str
    base_currency: str
    quote_currency: str
    applied_rate: str
    selected_source: str
    converted_amount: str


class ConvertDailyResponse(BaseModel):
    lines: list[ConvertDailyLineResponse]
    count: int


class ApplyMonthEndLineRequest(BaseModel):
    reference: str | None = None
    amount: Decimal


class ApplyMonthEndRequest(BaseModel):
    period_year: int = Field(ge=_MIN_SUPPORTED_YEAR, le=_MAX_SUPPORTED_YEAR)
    period_month: int = Field(ge=1, le=12)
    base_currency: str
    quote_currency: str
    lines: list[ApplyMonthEndLineRequest] = Field(min_length=1, max_length=10000)
    approval_reason: str = Field(min_length=3, max_length=1000)

    @field_validator("base_currency", "quote_currency", mode="before")
    @classmethod
    def _validate_currency(cls, value: Any) -> str:
        return normalize_currency_code(str(value))

    @model_validator(mode="after")
    def _validate_pair(self) -> "ApplyMonthEndRequest":
        base, quote = normalize_currency_pair(self.base_currency, self.quote_currency)
        if base == quote:
            raise ValueError("base_currency and quote_currency must differ")
        self.base_currency = base
        self.quote_currency = quote
        return self


class ApplyMonthEndLineResponse(BaseModel):
    reference: str | None
    amount: str
    converted_amount: str
    applied_rate: str


class ApplyMonthEndResponse(BaseModel):
    period_year: int
    period_month: int
    base_currency: str
    quote_currency: str
    selected_rate: str
    selected_source: str
    lines: list[ApplyMonthEndLineResponse]
    count: int
    lock_rate_id: str | None


class FxVarianceRequest(BaseModel):
    period_year: int = Field(ge=_MIN_SUPPORTED_YEAR, le=_MAX_SUPPORTED_YEAR)
    period_month: int = Field(ge=1, le=12)
    base_currency: str
    quote_currency: str
    expected_difference: Decimal
    actual_difference: Decimal
    entity_name: str | None = None
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("base_currency", "quote_currency", mode="before")
    @classmethod
    def _validate_currency(cls, value: Any) -> str:
        return normalize_currency_code(str(value))

    @model_validator(mode="after")
    def _validate_pair(self) -> "FxVarianceRequest":
        base, quote = normalize_currency_pair(self.base_currency, self.quote_currency)
        if base == quote:
            raise ValueError("base_currency and quote_currency must differ")
        self.base_currency = base
        self.quote_currency = quote
        return self


class FxVarianceResponse(BaseModel):
    variance_id: str
    period_year: int
    period_month: int
    base_currency: str
    quote_currency: str
    expected_difference: str
    actual_difference: str
    fx_variance: str
    created_at: str
