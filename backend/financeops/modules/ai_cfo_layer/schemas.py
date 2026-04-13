from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field

Severity = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]


class AnomalyRow(BaseModel):
    id: uuid.UUID | None = None
    metric_name: str
    anomaly_type: str
    deviation_value: Decimal
    severity: Severity
    explanation: str
    facts: dict[str, Any] = Field(default_factory=dict)
    lineage: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None


class AnomalyResponse(BaseModel):
    rows: list[AnomalyRow]
    validation: dict[str, Any] = Field(default_factory=dict)
    generation_method: str = "deterministic"


class VarianceDriverRow(BaseModel):
    account_code: str
    account_name: str
    variance_value: Decimal
    variance_percent: Decimal | None = None


class VarianceExplanationResponse(BaseModel):
    metric_name: str
    comparison: str
    current_value: Decimal
    previous_value: Decimal
    variance_value: Decimal
    variance_percent: Decimal | None = None
    explanation: str
    top_drivers: list[VarianceDriverRow] = Field(default_factory=list)
    fact_basis: dict[str, Any] = Field(default_factory=dict)
    validation_passed: bool = True


class RecommendationRow(BaseModel):
    id: uuid.UUID | None = None
    recommendation_type: str
    severity: Severity
    message: str
    evidence: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None


class RecommendationsResponse(BaseModel):
    rows: list[RecommendationRow]
    validation: dict[str, Any] = Field(default_factory=dict)


class NarrativeResponse(BaseModel):
    summary: str
    highlights: list[str]
    drivers: list[str]
    risks: list[str]
    actions: list[str]
    fact_basis: dict[str, Any] = Field(default_factory=dict)
    validation_passed: bool = True
    generation_method: str = "deterministic"


class SuggestedJournalLine(BaseModel):
    account_code: str
    entry_type: Literal["DEBIT", "CREDIT"]
    amount: Decimal
    memo: str | None = None


class SuggestedJournal(BaseModel):
    title: str
    reason: str
    suggested_date: date
    lines: list[SuggestedJournalLine]
    evidence: dict[str, Any] = Field(default_factory=dict)


class SuggestionsResponse(BaseModel):
    rows: list[SuggestedJournal]
    validation: dict[str, Any] = Field(default_factory=dict)


class AuditSampleRow(BaseModel):
    journal_id: uuid.UUID
    journal_number: str
    journal_date: date
    total_debit: Decimal
    total_credit: Decimal
    status: str
    source: str
    external_reference_id: str | None = None
    risk_score: Decimal
    selection_reason: str


class AuditSamplesResponse(BaseModel):
    mode: Literal["random", "risk_based"]
    sample_size: int
    rows: list[AuditSampleRow]
    fact_basis: dict[str, Any] = Field(default_factory=dict)

