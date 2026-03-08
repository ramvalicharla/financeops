from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ConsolidatedMetricRow:
    metric_code: str
    aggregated_value: Decimal
    entity_count: int
    currency_code: str
    source_metric_refs: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ConsolidatedVarianceRow:
    metric_code: str
    comparison_type: str
    base_value: Decimal
    current_value: Decimal
    variance_value: Decimal
    variance_pct: Decimal | None
    source_variance_refs: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ConsolidationRunSummary:
    run_id: UUID
    run_token: str
    run_status: str
    metric_count: int
    variance_count: int
    evidence_count: int

