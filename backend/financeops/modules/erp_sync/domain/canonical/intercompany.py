from __future__ import annotations

from decimal import Decimal

from pydantic import Field

from financeops.modules.erp_sync.domain.canonical.common import CanonicalDatasetBase, CanonicalLineBase


class CanonicalIntercompanyLine(CanonicalLineBase):
    dataset_token: str | None = None
    amount: Decimal = Decimal("0")
    status: str | None = None


class CanonicalIntercompanyTransactions(CanonicalDatasetBase):
    dataset_token: str  # SHA256 of full serialized content
    lines: list[CanonicalIntercompanyLine] = Field(default_factory=list)
    
    

