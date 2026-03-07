from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from financeops.modules.payroll_gl_reconciliation.domain.enums import (
    CoreDifferenceType,
    PayrollGlDifferenceType,
)


@dataclass(frozen=True)
class PayrollGlComparisonLine:
    line_key: str
    comparison_dimension_json: dict[str, Any]
    payroll_value: Decimal
    gl_value: Decimal
    variance_value: Decimal
    variance_abs: Decimal
    variance_pct: Decimal
    currency_code: str
    core_difference_type: CoreDifferenceType
    payroll_difference_type: PayrollGlDifferenceType
    materiality_flag: bool
    explanation_hint: str | None


@dataclass(frozen=True)
class PayrollGlComputedException:
    line_key: str
    exception_code: str
    severity: str
    message: str
    owner_role: str | None

