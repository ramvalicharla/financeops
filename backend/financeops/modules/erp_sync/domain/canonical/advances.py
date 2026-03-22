from __future__ import annotations

from decimal import Decimal

from pydantic import Field

from financeops.modules.erp_sync.domain.canonical.common import CanonicalDatasetBase, CanonicalLineBase


class CanonicalAdvanceLine(CanonicalLineBase):
    dataset_token: str | None = None
    amount: Decimal = Decimal("0")
    status: str | None = None


class CanonicalAdvances(CanonicalDatasetBase):
    dataset_token: str  # SHA256 of full serialized content
    lines: list[CanonicalAdvanceLine] = Field(default_factory=list)
    
    

