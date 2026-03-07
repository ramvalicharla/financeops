from __future__ import annotations

from decimal import Decimal
from typing import Any

from financeops.modules.mis_manager.application.canonical_dictionary_service import (
    CanonicalDictionaryService,
)
from financeops.modules.mis_manager.domain.entities import CanonicalMapping


class MappingService:
    def __init__(self, dictionary_service: CanonicalDictionaryService) -> None:
        self._dictionary = dictionary_service.get_dictionary()

    def map_rows_to_canonical_metrics(
        self, row_labels: list[str]
    ) -> list[CanonicalMapping]:
        mappings: list[CanonicalMapping] = []
        for label in row_labels:
            normalized = _normalize(label)
            metric_code = _match_metric(normalized, self._dictionary.metrics)
            confidence = Decimal("1.0000") if metric_code else Decimal("0.3000")
            mappings.append(
                CanonicalMapping(
                    source_label=label,
                    normalized_label=normalized,
                    canonical_metric_code=metric_code,
                    canonical_dimension_code=None,
                    confidence_score=confidence,
                )
            )
        return mappings

    def map_columns(self, headers: list[str]) -> list[dict[str, Any]]:
        mapped: list[dict[str, Any]] = []
        for ordinal, header in enumerate(headers, start=1):
            normalized = _normalize(header)
            if _looks_like_period(normalized):
                role = "period"
            elif normalized in self._dictionary.dimensions:
                role = "dimension"
            elif normalized in {"value", "amount", "period_value"}:
                role = "value"
            elif normalized in {"notes", "comment", "remarks"}:
                role = "notes"
            else:
                role = "metric_name"
            mapped.append(
                {
                    "source_column_label": header,
                    "normalized_column_label": normalized,
                    "column_role": role,
                    "ordinal_position": ordinal,
                    "canonical_dimension_code": normalized
                    if role == "dimension"
                    else None,
                    "canonical_metric_code": normalized
                    if role == "metric_name" and normalized in self._dictionary.metrics
                    else None,
                }
            )
        return mapped


def _normalize(value: str) -> str:
    return "_".join(value.strip().lower().split())


def _looks_like_period(value: str) -> bool:
    tokens = ("period", "month", "year", "fy", "q1", "q2", "q3", "q4")
    return any(token in value for token in tokens)


def _match_metric(
    normalized_label: str, canonical_metrics: tuple[str, ...]
) -> str | None:
    if normalized_label in canonical_metrics:
        return normalized_label
    prefix_hits = [
        metric
        for metric in canonical_metrics
        if normalized_label in metric or metric in normalized_label
    ]
    if len(prefix_hits) == 1:
        return prefix_hits[0]
    return None
