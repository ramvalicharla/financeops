from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class PrepaidScheduleCreateRequest(BaseModel):
    entity_id: uuid.UUID
    reference_number: str
    description: str
    prepaid_type: str
    vendor_name: str | None = None
    invoice_number: str | None = None
    total_amount: Decimal
    coverage_start: date
    coverage_end: date
    amortisation_method: str = "SLM"
    coa_prepaid_account_id: uuid.UUID | None = None
    coa_expense_account_id: uuid.UUID | None = None


class PrepaidScheduleUpdateRequest(BaseModel):
    description: str | None = None
    prepaid_type: str | None = None
    vendor_name: str | None = None
    invoice_number: str | None = None
    status: str | None = None
    coa_prepaid_account_id: uuid.UUID | None = None
    coa_expense_account_id: uuid.UUID | None = None


class PrepaidScheduleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    entity_id: uuid.UUID
    reference_number: str
    description: str
    prepaid_type: str
    vendor_name: str | None = None
    invoice_number: str | None = None
    total_amount: Decimal
    amortised_amount: Decimal
    remaining_amount: Decimal
    coverage_start: date
    coverage_end: date
    amortisation_method: str
    coa_prepaid_account_id: uuid.UUID | None = None
    coa_expense_account_id: uuid.UUID | None = None
    status: str
    created_at: datetime
    updated_at: datetime | None = None


class PrepaidRunPeriodRequest(BaseModel):
    entity_id: uuid.UUID
    period_start: date
    period_end: date


class PrepaidAmortisationEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    entity_id: uuid.UUID
    schedule_id: uuid.UUID
    period_start: date
    period_end: date
    amortisation_amount: Decimal
    is_last_period: bool
    run_reference: str
    created_at: datetime


class PrepaidScheduleLineResponse(BaseModel):
    period_start: date
    period_end: date
    amount: Decimal
    is_last_period: bool
    is_actual: bool
    status: str


__all__ = [
    "PrepaidScheduleCreateRequest",
    "PrepaidScheduleUpdateRequest",
    "PrepaidScheduleResponse",
    "PrepaidRunPeriodRequest",
    "PrepaidAmortisationEntryResponse",
    "PrepaidScheduleLineResponse",
]
