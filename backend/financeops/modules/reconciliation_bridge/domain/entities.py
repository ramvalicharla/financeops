from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from financeops.modules.reconciliation_bridge.domain.enums import (
    DifferenceType,
    ExceptionSeverity,
    ReconciliationStatus,
)


@dataclass(frozen=True)
class ComparableAmount:
    key: str
    dimensions: dict[str, Any]
    value: Decimal
    currency_code: str


@dataclass(frozen=True)
class ReconciliationComputedLine:
    line_key: str
    comparison_dimension_json: dict[str, Any]
    source_a_value: Decimal
    source_b_value: Decimal
    variance_value: Decimal
    variance_abs: Decimal
    variance_pct: Decimal
    currency_code: str
    reconciliation_status: ReconciliationStatus
    difference_type: DifferenceType
    materiality_flag: bool
    explanation_hint: str | None


@dataclass(frozen=True)
class ReconciliationComputedException:
    line_key: str
    exception_code: str
    severity: ExceptionSeverity
    message: str
    owner_role: str | None
