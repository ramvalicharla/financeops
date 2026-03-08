from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Any

from financeops.modules.multi_entity_consolidation.domain.entities import (
    ConsolidatedMetricRow,
    ConsolidatedVarianceRow,
)
from financeops.modules.multi_entity_consolidation.domain.invariants import q6


class AggregationService:
    def aggregate_metrics(
        self,
        *,
        metric_rows: list[object],
        allowed_entity_ids: set[str],
    ) -> list[ConsolidatedMetricRow]:
        totals: dict[tuple[str, str], Decimal] = defaultdict(lambda: Decimal("0"))
        counts: dict[tuple[str, str], set[str]] = defaultdict(set)
        refs: dict[tuple[str, str], list[str]] = defaultdict(list)

        for row in metric_rows:
            entity_id = str(row.dimension_json.get("legal_entity", ""))
            if allowed_entity_ids and entity_id and entity_id not in allowed_entity_ids:
                continue
            metric_code = str(row.metric_code)
            currency = str(row.dimension_json.get("currency_code", "XXX"))[:3].upper()
            key = (metric_code, currency)
            totals[key] += Decimal(row.metric_value)
            if entity_id:
                counts[key].add(entity_id)
            refs[key].append(str(row.id))

        result: list[ConsolidatedMetricRow] = []
        for key in sorted(totals.keys(), key=lambda value: (value[0], value[1])):
            metric_code, currency_code = key
            result.append(
                ConsolidatedMetricRow(
                    metric_code=metric_code,
                    aggregated_value=q6(totals[key]),
                    entity_count=max(1, len(counts[key])),
                    currency_code=currency_code,
                    source_metric_refs=sorted(refs[key]),
                )
            )
        return result

    def aggregate_variances(
        self,
        *,
        variance_rows: list[object],
        allowed_entity_ids: set[str],
    ) -> list[ConsolidatedVarianceRow]:
        bucket: dict[tuple[str, str], dict[str, Any]] = {}
        for row in variance_rows:
            key = (str(row.metric_code), str(row.comparison_type))
            existing = bucket.get(key)
            if existing is None:
                existing = {
                    "base": Decimal("0"),
                    "current": Decimal("0"),
                    "variance": Decimal("0"),
                    "refs": [],
                }
                bucket[key] = existing
            existing["base"] += Decimal(row.baseline_value)
            existing["current"] += Decimal(row.current_value)
            existing["variance"] += Decimal(row.variance_abs)
            existing["refs"].append(str(row.id))

        results: list[ConsolidatedVarianceRow] = []
        for key in sorted(bucket.keys(), key=lambda value: (value[0], value[1])):
            metric_code, comparison_type = key
            current = q6(bucket[key]["current"])
            base = q6(bucket[key]["base"])
            variance_value = q6(bucket[key]["variance"])
            variance_pct: Decimal | None
            if base == Decimal("0"):
                variance_pct = None
            else:
                variance_pct = q6((variance_value / base) * Decimal("100"))
            results.append(
                ConsolidatedVarianceRow(
                    metric_code=metric_code,
                    comparison_type=comparison_type,
                    base_value=base,
                    current_value=current,
                    variance_value=variance_value,
                    variance_pct=variance_pct,
                    source_variance_refs=sorted(bucket[key]["refs"]),
                )
            )
        return results
