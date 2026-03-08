from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class CashFlowLineComputation:
    line_code: str
    source_metric_code: str
    source_value: Decimal
    sign_multiplier: Decimal
    computed_value: Decimal
