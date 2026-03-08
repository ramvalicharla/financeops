from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class OwnershipAttributedMetric:
    line_no: int
    scope_code: str
    metric_code: str
    source_consolidated_value: Decimal
    ownership_weight_applied: Decimal
    attributed_value: Decimal
    minority_interest_value_nullable: Decimal | None
    reporting_currency_code_nullable: str | None


@dataclass(frozen=True, slots=True)
class OwnershipAttributedVariance:
    line_no: int
    scope_code: str
    metric_code: str
    variance_code: str
    source_current_value: Decimal
    source_comparison_value: Decimal
    ownership_weight_applied: Decimal
    attributed_current_value: Decimal
    attributed_comparison_value: Decimal
    attributed_variance_abs: Decimal
    attributed_variance_pct: Decimal | None
    attributed_variance_bps: Decimal | None
    minority_interest_value_nullable: Decimal | None
