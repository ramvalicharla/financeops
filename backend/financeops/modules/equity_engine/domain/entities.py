from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class EquityLineComputation:
    line_code: str
    opening_balance: Decimal
    movement_amount: Decimal
    closing_balance: Decimal
