from __future__ import annotations

from enum import Enum


class DefinitionStatus(str, Enum):
    CANDIDATE = "candidate"
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    REJECTED = "rejected"


class MetricFormulaType(str, Enum):
    SUM = "sum"
    RATIO = "ratio"
    DIFFERENCE = "difference"
    DIRECT = "direct"
    CUSTOM_EXPRESSION = "custom_expression"


class MetricDirectionality(str, Enum):
    HIGHER_IS_BETTER = "higher_is_better"
    LOWER_IS_BETTER = "lower_is_better"
    NEUTRAL = "neutral"
    CONTEXTUAL = "contextual"


class ComparisonType(str, Enum):
    MOM_ABS_PCT = "mom_abs_pct"
    YOY_ABS_PCT = "yoy_abs_pct"
    ACTUAL_VS_BUDGET_ABS_PCT = "actual_vs_budget_abs_pct"
    ACTUAL_VS_FORECAST_ABS_PCT = "actual_vs_forecast_abs_pct"
    BASIS_POINTS_CHANGE = "basis_points_change"
    DAYS_CHANGE = "days_change"


class TrendType(str, Enum):
    ROLLING_AVERAGE = "rolling_average"
    TRAILING_TOTAL = "trailing_total"
    DIRECTIONAL = "directional"


class RunStatus(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class FavorableStatus(str, Enum):
    FAVORABLE = "favorable"
    UNFAVORABLE = "unfavorable"
    NEUTRAL = "neutral"
