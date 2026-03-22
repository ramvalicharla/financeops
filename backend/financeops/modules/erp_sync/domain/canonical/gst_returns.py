from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel
from pydantic import Field

from financeops.modules.erp_sync.domain.canonical.common import CanonicalDatasetBase, CanonicalLineBase


class CanonicalGstReturnLine(CanonicalLineBase):
    dataset_token: str | None = None
    return_type: str
    taxable_value: Decimal = Decimal("0")
    tax_value: Decimal = Decimal("0")


class CanonicalGstReturn(CanonicalDatasetBase):
    dataset_token: str  # SHA256 of full serialized content
    lines: list[CanonicalGstReturnLine] = Field(default_factory=list)


class CanonicalGSTR9Summary(BaseModel):
    financial_year: str  # "2024-25"
    entity_id: str
    gstin: str
    total_outward_supplies: Decimal
    total_inward_supplies: Decimal
    total_itc_availed: Decimal
    total_tax_paid: Decimal
    filing_status: str  # FILED / PENDING / NIL
    filing_date: date | None = None
    dataset_token: str


class CanonicalGSTR9C(BaseModel):
    financial_year: str
    entity_id: str
    gstin: str
    turnover_as_per_books: Decimal
    turnover_as_per_gst: Decimal
    variance: Decimal
    reason_for_variance: str | None = None
    auditor_certified: bool
    filing_status: str
    dataset_token: str


# Backward-compatible aliases used by existing imports.
CanonicalGstr9Stub = CanonicalGSTR9Summary
CanonicalGstr9cStub = CanonicalGSTR9C

