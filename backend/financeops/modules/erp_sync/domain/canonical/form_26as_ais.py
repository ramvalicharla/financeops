from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class Canonical26ASEntry(BaseModel):
    deductor_tan: str
    deductor_name: str
    tds_section: str
    payment_date: date
    amount_paid: Decimal
    tds_deducted: Decimal
    tds_deposited: Decimal
    certificate_number: str | None
    remarks: str | None
    pii_masked: bool


class CanonicalForm26AS(BaseModel):
    financial_year: str
    entity_id: str
    pan_number: str | None  # masked — last 4 only
    entries: list[Canonical26ASEntry]
    total_tds_as_per_26as: Decimal
    assessment_year: str
    pii_masked: bool
    dataset_token: str


class CanonicalAISEntry(BaseModel):
    transaction_type: str
    source: str
    amount: Decimal
    tds_tcs: Decimal
    financial_year: str
    pii_masked: bool


class CanonicalAISRegister(BaseModel):
    financial_year: str
    entity_id: str
    entries: list[CanonicalAISEntry]
    total_income_reported: Decimal
    total_tds_tcs: Decimal
    pii_masked: bool
    dataset_token: str
