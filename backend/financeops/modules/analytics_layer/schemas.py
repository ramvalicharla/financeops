from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class AnalyticsMetricRow(BaseModel):
    metric_name: str
    metric_value: Decimal
    unit: str = "NUMBER"
    dimension: dict[str, Any] = Field(default_factory=dict)


class AnalyticsSnapshotRef(BaseModel):
    snapshot_id: uuid.UUID
    snapshot_type: str
    as_of_date: date
    period_from: date | None = None
    period_to: date | None = None


class KpiResponse(BaseModel):
    rows: list[AnalyticsMetricRow]
    snapshot: AnalyticsSnapshotRef
    lineage: dict[str, Any] = Field(default_factory=dict)


class VarianceMetricRow(BaseModel):
    metric_name: str
    current_value: Decimal
    previous_value: Decimal
    variance_value: Decimal
    variance_percent: Decimal | None = None


class AccountVarianceRow(BaseModel):
    account_code: str
    account_name: str
    current_value: Decimal
    previous_value: Decimal
    variance_value: Decimal
    variance_percent: Decimal | None = None


class VarianceResponse(BaseModel):
    comparison: str
    current_period: dict[str, date]
    previous_period: dict[str, date]
    metric_variances: list[VarianceMetricRow]
    account_variances: list[AccountVarianceRow]
    snapshot: AnalyticsSnapshotRef


class TrendPoint(BaseModel):
    period: str
    value: Decimal


class TrendSeries(BaseModel):
    metric_name: str
    points: list[TrendPoint]


class TrendResponse(BaseModel):
    frequency: str
    series: list[TrendSeries]
    snapshot: AnalyticsSnapshotRef


class RatioResponse(BaseModel):
    rows: list[AnalyticsMetricRow]
    snapshot: AnalyticsSnapshotRef
    lineage: dict[str, Any] = Field(default_factory=dict)


class BudgetVarianceRow(BaseModel):
    account_id: uuid.UUID
    account_code: str
    account_name: str
    budget_amount: Decimal
    actual_amount: Decimal
    variance_value: Decimal
    variance_percent: Decimal | None = None


class BudgetVarianceResponse(BaseModel):
    period: str
    org_entity_id: uuid.UUID
    rows: list[BudgetVarianceRow]
    snapshot: AnalyticsSnapshotRef


class DrilldownJournalRow(BaseModel):
    journal_id: uuid.UUID
    journal_number: str
    journal_date: date
    status: str
    source_ref: str | None = None


class DrilldownGlRow(BaseModel):
    gl_entry_id: uuid.UUID
    account_code: str
    account_name: str
    debit_amount: Decimal
    credit_amount: Decimal
    source_ref: str | None = None
    created_at: datetime


class DrilldownAccountRow(BaseModel):
    account_code: str
    account_name: str
    amount: Decimal


class DrilldownResponse(BaseModel):
    metric_name: str
    accounts: list[DrilldownAccountRow]
    journals: list[DrilldownJournalRow]
    gl_entries: list[DrilldownGlRow]
    lineage: dict[str, Any] = Field(default_factory=dict)


class AlertCreateRequest(BaseModel):
    metric_name: str = Field(..., min_length=1, max_length=64)
    threshold: Decimal
    condition: str = Field(..., pattern="^(GT|LT|ABS_GT)$")
    description: str | None = None


class AlertRow(BaseModel):
    id: uuid.UUID
    metric_name: str
    threshold: Decimal
    condition: str
    description: str | None
    created_at: datetime


class AlertEvaluationRow(BaseModel):
    metric_name: str
    metric_value: Decimal
    threshold: Decimal
    condition: str
    triggered: bool
    description: str | None = None

