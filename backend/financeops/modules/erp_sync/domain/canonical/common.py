from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class CanonicalLineBase(BaseModel):
    entity_id: str
    currency: str = Field(min_length=3, max_length=3)
    dimension_refs: dict[str, str] = Field(default_factory=dict)
    source_entry_id: str | None = None
    attachment_references: list[str] = Field(default_factory=list)
    pii_masked: bool = False


class CanonicalDatasetBase(BaseModel):
    entity_id: str
    currency: str = Field(min_length=3, max_length=3)
    from_date: date | None = None
    to_date: date | None = None
    as_at_date: date | None = None
    line_count: int = 0
    erp_reported_line_count: int | None = None
    erp_reported_total_debits: Decimal | None = None
    erp_reported_total_credits: Decimal | None = None
    erp_reported_total_amount: Decimal | None = None
    dataset_token: str
    
