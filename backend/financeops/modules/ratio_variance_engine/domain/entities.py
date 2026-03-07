from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from financeops.modules.ratio_variance_engine.domain.enums import FavorableStatus


@dataclass(frozen=True)
class ComputedMetric:
    metric_code: str
    unit_type: str
    dimension_json: dict[str, Any]
    metric_value: Decimal
    favorable_status: FavorableStatus
    materiality_flag: bool
    source_summary_json: dict[str, Any]


@dataclass(frozen=True)
class ComputedVariance:
    metric_code: str
    comparison_type: str
    base_period: str | None
    current_value: Decimal
    baseline_value: Decimal
    variance_abs: Decimal
    variance_pct: Decimal
    variance_bps: Decimal
    days_change: Decimal
    favorable_status: FavorableStatus
    materiality_flag: bool
    explanation_hint: str | None


@dataclass(frozen=True)
class ComputedTrend:
    metric_code: str
    trend_type: str
    window_size: int
    trend_value: Decimal
    trend_direction: str
    source_summary_json: dict[str, Any]
