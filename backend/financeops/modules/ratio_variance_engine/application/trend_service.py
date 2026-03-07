from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from financeops.db.models.ratio_variance_engine import TrendDefinition
from financeops.modules.ratio_variance_engine.domain.entities import ComputedTrend
from financeops.modules.ratio_variance_engine.domain.invariants import q6
from financeops.modules.ratio_variance_engine.domain.value_objects import (
    DefinitionVersionTokenInput,
)
from financeops.modules.ratio_variance_engine.infrastructure.token_builder import (
    build_definition_version_token,
)


class TrendService:
    def version_token(self, definitions: list[TrendDefinition]) -> str:
        rows = [
            {
                "definition_code": item.definition_code,
                "metric_code": item.metric_code,
                "trend_type": item.trend_type,
                "window_size": item.window_size,
                "configuration_json": item.configuration_json,
                "effective_from": item.effective_from.isoformat(),
                "status": item.status,
            }
            for item in sorted(definitions, key=lambda row: (row.definition_code, row.id))
        ]
        return build_definition_version_token(DefinitionVersionTokenInput(rows=rows))

    def compute_trends(
        self,
        *,
        definitions: list[TrendDefinition],
        metric_values: dict[str, Decimal],
        prior_series_lookup: dict[str, list[tuple[date, Decimal]]],
    ) -> list[ComputedTrend]:
        output: list[ComputedTrend] = []
        for definition in sorted(definitions, key=lambda row: (row.definition_code, row.id)):
            metric_code = definition.metric_code
            current = q6(metric_values.get(metric_code, Decimal("0")))
            prior = prior_series_lookup.get(metric_code, [])
            window = max(1, int(definition.window_size))
            sequence = [current] + [q6(value) for _, value in prior[: window - 1]]
            trend_value = self._trend_value(definition.trend_type, sequence)
            previous = q6(prior[0][1]) if prior else Decimal("0")
            direction = self._direction(current=current, previous=previous)
            output.append(
                ComputedTrend(
                    metric_code=metric_code,
                    trend_type=definition.trend_type,
                    window_size=window,
                    trend_value=trend_value,
                    trend_direction=direction,
                    source_summary_json={
                        "prior_points_used": len(sequence) - 1,
                    },
                )
            )
        output.sort(key=lambda row: (row.metric_code, row.trend_type, row.window_size))
        return output

    def _trend_value(self, trend_type: str, sequence: list[Decimal]) -> Decimal:
        if not sequence:
            return Decimal("0")
        if trend_type == "trailing_total":
            total = Decimal("0")
            for value in sequence:
                total = q6(total + value)
            return q6(total)
        if trend_type == "directional":
            return q6(sequence[0] - (sequence[1] if len(sequence) > 1 else Decimal("0")))
        total = Decimal("0")
        for value in sequence:
            total = q6(total + value)
        return q6(total / Decimal(len(sequence)))

    def _direction(self, *, current: Decimal, previous: Decimal) -> str:
        if current > previous:
            return "up"
        if current < previous:
            return "down"
        return "flat"
