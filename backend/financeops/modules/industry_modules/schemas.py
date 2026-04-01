from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


ModuleStatus = Literal["ENABLED", "DISABLED"]
DepreciationMethod = Literal["SLM", "WDV"]


class ModuleToggleRequest(BaseModel):
    configuration_json: dict[str, Any] | None = None


class ModuleResponse(BaseModel):
    module_name: str
    status: ModuleStatus
    configuration_json: dict[str, Any]
    updated_at: datetime


class LeaseCreateRequest(BaseModel):
    entity_id: uuid.UUID
    lease_start_date: date
    lease_end_date: date
    lease_payment: Decimal = Field(..., gt=Decimal("0"))
    discount_rate: Decimal = Field(..., ge=Decimal("0"))
    lease_type: str = Field(..., min_length=1, max_length=32)
    currency: str = Field(default="INR", min_length=3, max_length=3)
    rou_asset_account_code: str | None = Field(default=None, min_length=1, max_length=32)
    lease_liability_account_code: str | None = Field(default=None, min_length=1, max_length=32)

    @field_validator("lease_payment", "discount_rate", mode="before")
    @classmethod
    def _coerce_decimal(cls, value: object) -> Decimal:
        return Decimal(str(value))

    @model_validator(mode="after")
    def _validate_dates(self) -> "LeaseCreateRequest":
        if self.lease_end_date < self.lease_start_date:
            raise ValueError("lease_end_date must be on/after lease_start_date.")
        return self


class LeaseScheduleRow(BaseModel):
    period_number: int
    period_date: date
    opening_liability: Decimal
    interest_expense: Decimal
    lease_payment: Decimal
    closing_liability: Decimal
    rou_asset_value: Decimal
    depreciation: Decimal


class LeaseCreateResponse(BaseModel):
    lease_id: uuid.UUID
    draft_journal_id: uuid.UUID
    periods: int


class RevenueObligationInput(BaseModel):
    obligation_type: str = Field(..., min_length=1, max_length=64)
    allocation_value: Decimal = Field(..., gt=Decimal("0"))

    @field_validator("allocation_value", mode="before")
    @classmethod
    def _coerce_decimal(cls, value: object) -> Decimal:
        return Decimal(str(value))


class RevenueContractCreateRequest(BaseModel):
    entity_id: uuid.UUID
    customer_id: str = Field(..., min_length=1, max_length=128)
    contract_start_date: date
    contract_end_date: date
    contract_value: Decimal = Field(..., gt=Decimal("0"))
    obligations: list[RevenueObligationInput] = Field(..., min_length=1)
    receivable_account_code: str | None = Field(default=None, min_length=1, max_length=32)
    revenue_account_code: str | None = Field(default=None, min_length=1, max_length=32)

    @field_validator("contract_value", mode="before")
    @classmethod
    def _coerce_decimal(cls, value: object) -> Decimal:
        return Decimal(str(value))

    @model_validator(mode="after")
    def _validate_contract(self) -> "RevenueContractCreateRequest":
        if self.contract_end_date < self.contract_start_date:
            raise ValueError("contract_end_date must be on/after contract_start_date.")
        total_allocation = sum(item.allocation_value for item in self.obligations)
        if total_allocation != self.contract_value:
            raise ValueError(
                f"Total allocation {total_allocation} must equal contract_value {self.contract_value}."
            )
        return self


class RevenueScheduleRow(BaseModel):
    obligation_type: str
    period_number: int
    recognition_date: date
    revenue_amount: Decimal


class RevenueContractCreateResponse(BaseModel):
    contract_id: uuid.UUID
    draft_journal_id: uuid.UUID
    periods: int


class FixedAssetCreateRequest(BaseModel):
    entity_id: uuid.UUID
    asset_name: str = Field(..., min_length=1, max_length=256)
    cost: Decimal = Field(..., gt=Decimal("0"))
    useful_life_years: int = Field(..., ge=1, le=100)
    depreciation_method: DepreciationMethod
    residual_value: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))
    asset_account_code: str | None = Field(default=None, min_length=1, max_length=32)
    payable_account_code: str | None = Field(default=None, min_length=1, max_length=32)

    @field_validator("cost", "residual_value", mode="before")
    @classmethod
    def _coerce_decimal(cls, value: object) -> Decimal:
        return Decimal(str(value))

    @model_validator(mode="after")
    def _validate_residual(self) -> "FixedAssetCreateRequest":
        if self.residual_value > self.cost:
            raise ValueError("residual_value cannot exceed cost.")
        return self


class AssetScheduleRow(BaseModel):
    period_number: int
    period_date: date
    depreciation: Decimal
    net_book_value: Decimal


class FixedAssetCreateResponse(BaseModel):
    asset_id: uuid.UUID
    draft_journal_id: uuid.UUID
    periods: int


class PrepaidCreateRequest(BaseModel):
    entity_id: uuid.UUID
    prepaid_name: str = Field(..., min_length=1, max_length=255)
    start_date: date
    end_date: date
    total_amount: Decimal = Field(..., gt=Decimal("0"))
    prepaid_account_code: str | None = Field(default=None, min_length=1, max_length=32)
    cash_account_code: str | None = Field(default=None, min_length=1, max_length=32)

    @field_validator("total_amount", mode="before")
    @classmethod
    def _coerce_decimal(cls, value: object) -> Decimal:
        return Decimal(str(value))

    @model_validator(mode="after")
    def _validate_dates(self) -> "PrepaidCreateRequest":
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on/after start_date.")
        return self


class AccrualCreateRequest(BaseModel):
    entity_id: uuid.UUID
    accrual_name: str = Field(..., min_length=1, max_length=255)
    start_date: date
    end_date: date
    total_amount: Decimal = Field(..., gt=Decimal("0"))
    expense_account_code: str | None = Field(default=None, min_length=1, max_length=32)
    accrued_liability_account_code: str | None = Field(default=None, min_length=1, max_length=32)

    @field_validator("total_amount", mode="before")
    @classmethod
    def _coerce_decimal(cls, value: object) -> Decimal:
        return Decimal(str(value))

    @model_validator(mode="after")
    def _validate_dates(self) -> "AccrualCreateRequest":
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on/after start_date.")
        return self


class ScheduleBatchCreateResponse(BaseModel):
    schedule_batch_id: uuid.UUID
    draft_journal_id: uuid.UUID
    periods: int

