from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class SelectedRate:
    multiplier: Decimal
    rate_type: str
    rate_ref: str
    source_currency: str
    reporting_currency: str


@dataclass(frozen=True, slots=True)
class TranslatedMetricRow:
    line_no: int
    source_metric_result_id: str
    metric_code: str
    source_currency_code: str
    reporting_currency_code: str
    applied_rate_type: str
    applied_rate_ref: str
    applied_rate_value: Decimal
    source_value: Decimal
    translated_value: Decimal
    lineage_json: dict[str, str] = field(default_factory=dict)

