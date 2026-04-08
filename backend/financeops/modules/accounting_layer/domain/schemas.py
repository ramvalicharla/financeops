from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class JVLineCreate(BaseModel):
    account_code: str = Field(..., min_length=1, max_length=32)
    account_name: str | None = None
    entry_type: str = Field(..., pattern="^(DEBIT|CREDIT)$")
    amount: Decimal = Field(..., gt=Decimal("0"))
    currency: str = Field(default="INR", min_length=3, max_length=3)
    transaction_currency: str | None = Field(default=None, min_length=3, max_length=3)
    functional_currency: str | None = Field(default=None, min_length=3, max_length=3)
    fx_rate: Decimal | None = Field(default=None, gt=Decimal("0"))
    base_amount: Decimal | None = None
    entity_id: uuid.UUID | None = None
    location_id: uuid.UUID | None = None
    cost_centre_id: uuid.UUID | None = None
    narration: str | None = None
    tax_code: str | None = None
    is_tax_line: bool = False

    @field_validator("amount", "fx_rate", mode="before")
    @classmethod
    def _coerce_decimal(cls, value: object) -> Decimal | None:
        if value is None:
            return None
        return Decimal(str(value))


class JVLineResponse(BaseModel):
    id: uuid.UUID
    jv_id: uuid.UUID
    jv_version: int
    line_number: int
    account_code: str
    account_name: str | None
    entry_type: str
    amount: Decimal
    currency: str
    transaction_currency: str | None = None
    functional_currency: str | None = None
    fx_rate: Decimal | None
    amount_inr: Decimal | None
    base_amount: Decimal | None = None
    entity_id: uuid.UUID
    location_id: uuid.UUID | None
    cost_centre_id: uuid.UUID | None
    narration: str | None
    tax_code: str | None
    is_tax_line: bool

    model_config = {"from_attributes": True}


class JVCreate(BaseModel):
    entity_id: uuid.UUID
    period_date: date
    fiscal_year: int = Field(..., ge=2000, le=2100)
    fiscal_period: int = Field(..., ge=1, le=12)
    description: str | None = None
    reference: str | None = None
    currency: str = Field(default="INR", min_length=3, max_length=3)
    location_id: uuid.UUID | None = None
    cost_centre_id: uuid.UUID | None = None
    workflow_instance_id: uuid.UUID | None = None
    lines: list[JVLineCreate] | None = None

    @model_validator(mode="after")
    def _validate_lines_balance(self) -> JVCreate:
        if not self.lines:
            return self
        total_debit = sum(ln.amount for ln in self.lines if ln.entry_type == "DEBIT")
        total_credit = sum(ln.amount for ln in self.lines if ln.entry_type == "CREDIT")
        if total_debit != total_credit:
            raise ValueError(
                f"Lines are not balanced: debit={total_debit}, credit={total_credit}"
            )
        return self


class JVUpdateLines(BaseModel):
    lines: list[JVLineCreate] = Field(..., min_length=2)
    expected_version: int = Field(..., ge=1)

    @model_validator(mode="after")
    def _validate_balance(self) -> JVUpdateLines:
        total_debit = sum(ln.amount for ln in self.lines if ln.entry_type == "DEBIT")
        total_credit = sum(ln.amount for ln in self.lines if ln.entry_type == "CREDIT")
        if total_debit != total_credit:
            raise ValueError(
                f"Lines not balanced: debit={total_debit}, credit={total_credit}"
            )
        return self


class JVTransitionRequest(BaseModel):
    to_status: str
    comment: str | None = None
    expected_version: int = Field(..., ge=1)


class JVStateEventResponse(BaseModel):
    id: uuid.UUID
    jv_id: uuid.UUID
    jv_version: int
    from_status: str
    to_status: str
    triggered_by: uuid.UUID
    actor_role: str | None
    comment: str | None
    occurred_at: datetime

    model_config = {"from_attributes": True}


class JVResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    entity_id: uuid.UUID
    location_id: uuid.UUID | None
    cost_centre_id: uuid.UUID | None
    jv_number: str
    status: str
    version: int
    period_date: date
    fiscal_year: int
    fiscal_period: int
    description: str | None
    reference: str | None
    total_debit: Decimal
    total_credit: Decimal
    currency: str
    created_by: uuid.UUID
    resubmission_count: int
    submitted_at: datetime | None
    first_reviewed_at: datetime | None
    decided_at: datetime | None
    created_at: datetime
    updated_at: datetime
    lines: list[JVLineResponse] = []

    model_config = {"from_attributes": True}


class JournalLineCreate(BaseModel):
    account_code: str | None = Field(default=None, min_length=1, max_length=50)
    tenant_coa_account_id: uuid.UUID | None = None
    debit: Decimal = Field(default=Decimal("0"))
    credit: Decimal = Field(default=Decimal("0"))
    memo: str | None = None
    transaction_currency: str | None = Field(default=None, min_length=3, max_length=3)
    functional_currency: str | None = Field(default=None, min_length=3, max_length=3)
    fx_rate: Decimal | None = Field(default=None, gt=Decimal("0"))
    base_amount: Decimal | None = None

    @field_validator("debit", "credit", mode="before")
    @classmethod
    def _coerce_line_decimal(cls, value: object) -> Decimal:
        if value is None:
            return Decimal("0")
        return Decimal(str(value))

    @field_validator("fx_rate", "base_amount", mode="before")
    @classmethod
    def _coerce_optional_decimal(cls, value: object) -> Decimal | None:
        if value is None:
            return None
        return Decimal(str(value))

    @model_validator(mode="after")
    def _validate_line_amounts(self) -> JournalLineCreate:
        if self.debit < 0 or self.credit < 0:
            raise ValueError("Debit and credit must be non-negative.")
        if self.debit > 0 and self.credit > 0:
            raise ValueError("A line cannot have both debit and credit.")
        if self.debit == 0 and self.credit == 0:
            raise ValueError("A line must have either debit or credit.")
        if not self.account_code and not self.tenant_coa_account_id:
            raise ValueError("Provide account_code or tenant_coa_account_id.")
        return self


class JournalCreate(BaseModel):
    org_entity_id: uuid.UUID
    journal_date: date
    reference: str | None = Field(default=None, max_length=128)
    narration: str | None = None
    lines: list[JournalLineCreate] = Field(..., min_length=2)

    @model_validator(mode="after")
    def _validate_balanced(self) -> JournalCreate:
        total_debit = sum(line.debit for line in self.lines)
        total_credit = sum(line.credit for line in self.lines)
        if total_debit != total_credit:
            raise ValueError(
                f"Journal is not balanced: debit={total_debit}, credit={total_credit}"
            )
        return self


class JournalLineResponse(BaseModel):
    line_number: int
    tenant_coa_account_id: uuid.UUID | None
    account_code: str
    account_name: str | None
    debit: Decimal
    credit: Decimal
    memo: str | None
    transaction_currency: str | None = None
    functional_currency: str | None = None
    fx_rate: Decimal | None = None
    base_amount: Decimal | None = None


class JournalResponse(BaseModel):
    id: uuid.UUID
    org_entity_id: uuid.UUID
    journal_number: str
    journal_date: date
    reference: str | None
    narration: str | None
    status: str
    posted_at: datetime | None
    total_debit: Decimal
    total_credit: Decimal
    currency: str
    created_by: uuid.UUID | None = None
    intent_id: uuid.UUID | None = None
    job_id: uuid.UUID | None = None
    approval_status: str | None = None
    lines: list[JournalLineResponse]


class JournalActionResponse(BaseModel):
    id: uuid.UUID
    status: str
    posted_at: datetime | None


class GovernedMutationResponse(BaseModel):
    intent_id: uuid.UUID
    status: str
    job_id: uuid.UUID | None
    next_action: str
    record_refs: dict[str, Any] | None = None


class TrialBalanceAccountRow(BaseModel):
    account_code: str
    account_name: str
    debit_sum: Decimal
    credit_sum: Decimal
    balance: Decimal


class TrialBalanceResponse(BaseModel):
    org_entity_id: uuid.UUID
    as_of_date: date
    from_date: date | None
    to_date: date | None
    total_debit: Decimal
    total_credit: Decimal
    rows: list[TrialBalanceAccountRow]


class PnLBreakdownRow(BaseModel):
    category: str
    account_code: str
    account_name: str
    amount: Decimal
    debit_sum: Decimal
    credit_sum: Decimal


class PnLResponse(BaseModel):
    org_entity_id: uuid.UUID
    from_date: date
    to_date: date
    revenue: Decimal
    cost_of_sales: Decimal
    gross_profit: Decimal
    operating_expense: Decimal
    operating_profit: Decimal
    other_income: Decimal
    other_expense: Decimal
    net_profit: Decimal
    breakdown: list[PnLBreakdownRow]


class BalanceSheetItem(BaseModel):
    account_code: str
    account_name: str
    account_type: str
    sub_type: str | None
    amount: Decimal


class BalanceSheetTotals(BaseModel):
    assets: Decimal
    liabilities: Decimal
    equity: Decimal
    liabilities_and_equity: Decimal


class BalanceSheetResponse(BaseModel):
    org_entity_id: uuid.UUID
    as_of_date: date
    assets: list[BalanceSheetItem]
    liabilities: list[BalanceSheetItem]
    equity: list[BalanceSheetItem]
    retained_earnings: Decimal
    totals: BalanceSheetTotals


class CashFlowBreakdownRow(BaseModel):
    category: str
    amount: Decimal


class CashFlowResponse(BaseModel):
    org_entity_id: uuid.UUID
    from_date: date
    to_date: date
    net_profit: Decimal
    non_cash_adjustments: Decimal
    working_capital_changes: Decimal
    operating_cash_flow: Decimal
    investing_cash_flow: Decimal
    financing_cash_flow: Decimal
    net_cash_flow: Decimal
    breakdown: list[CashFlowBreakdownRow]


class RevaluationRunRequest(BaseModel):
    org_entity_id: uuid.UUID
    as_of_date: date


class RevaluationRunResponse(BaseModel):
    run_id: str
    entity_id: str
    as_of_date: str
    functional_currency: str
    status: str
    adjustment_jv_id: str | None
    adjustment_pipeline: dict[str, Any] | None = None
    line_count: int
    total_fx_difference: str


class ApprovalRequest(BaseModel):
    decision: str = Field(..., pattern="^(APPROVED|REJECTED)$")
    decision_reason: str | None = None
    expected_version: int = Field(..., ge=1)
    idempotency_key: str | None = None
    delegated_from: uuid.UUID | None = None

    @field_validator("decision_reason", mode="after")
    @classmethod
    def reason_required_for_rejection(
        cls,
        value: str | None,
        info: Any,
    ) -> str | None:
        _ = info
        return value


class ApprovalResponse(BaseModel):
    id: uuid.UUID
    jv_id: uuid.UUID
    jv_version: int
    acted_by: uuid.UUID
    delegated_from: uuid.UUID | None
    actor_role: str
    decision: str
    decision_reason: str | None
    approval_level: int
    amount_threshold: Decimal | None
    acted_at: datetime

    model_config = {"from_attributes": True}


class SLATimerResponse(BaseModel):
    id: uuid.UUID
    jv_id: uuid.UUID
    review_sla_hours: int
    approval_sla_hours: int
    review_breached: bool
    approval_breached: bool
    review_breached_at: datetime | None
    approval_breached_at: datetime | None
    nudge_24h_sent: bool
    nudge_48h_sent: bool

    model_config = {"from_attributes": True}


class SLAMetricsResponse(BaseModel):
    total_jvs: int
    approved: int
    rejected: int
    pending: int
    avg_review_hours: float | None
    avg_decision_hours: float | None
