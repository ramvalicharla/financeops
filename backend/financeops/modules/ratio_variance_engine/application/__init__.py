from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from financeops.db.models.ratio_variance_engine import VarianceDefinition
from financeops.modules.ratio_variance_engine.application.materiality_service import (
    MaterialityService,
)
from financeops.modules.ratio_variance_engine.domain.entities import ComputedVariance
from financeops.modules.ratio_variance_engine.domain.invariants import (
    TEN_THOUSAND,
    assert_variance_invariant,
    q6,
)
from financeops.modules.ratio_variance_engine.domain.value_objects import (
    DefinitionVersionTokenInput,
)
from financeops.modules.ratio_variance_engine.infrastructure.token_builder import (
    build_definition_version_token,
)


class VarianceService:
    def version_token(self, definitions: list[VarianceDefinition]) -> str:
        rows = [
            {
                "definition_code": item.definition_code,
                "metric_code": item.metric_code,
                "comparison_type": item.comparison_type,
                "configuration_json": item.configuration_json,
                "effective_from": item.effective_from.isoformat(),
                "status": item.status,
            }
            for item in sorted(definitions, key=lambda row: (row.definition_code, row.id))
        ]
        return build_definition_version_token(DefinitionVersionTokenInput(rows=rows))

    def compute_variances(
        self,
        *,
        definitions: list[VarianceDefinition],
        metric_values: dict[str, Decimal],
        prior_series_lookup: dict[str, list[tuple[date, Decimal]]],
        scope_json: dict[str, Any],
        materiality_rule_json: dict[str, Any],
        directionality_by_metric: dict[str, str],
        materiality_service: MaterialityService,
    ) -> list[ComputedVariance]:
        output: list[ComputedVariance] = []
        for definition in sorted(definitions, key=lambda row: (row.definition_code, row.id)):
            metric_code = definition.metric_code
            current_value = q6(metric_values.get(metric_code, Decimal("0")))
            base_period, baseline_value = self._baseline(
                comparison_type=definition.comparison_type,
                metric_code=metric_code,
                current_value=current_value,
                prior_series=prior_series_lookup.get(metric_code, []),
                scope_json=scope_json,
            )
            variance_abs = q6(current_value - baseline_value)
            assert_variance_invariant(
                current=current_value,
                baseline=baseline_value,
                variance_abs=variance_abs,
            )
            variance_pct = self._pct(current_value=current_value, baseline_value=baseline_value)
            variance_bps = q6((current_value - baseline_value) * TEN_THOUSAND)
            days_change = q6(current_value - baseline_value)
            favorable = materiality_service.favorable_status(
                directionality=directionality_by_metric.get(metric_code, "neutral"),
                delta=variance_abs,
            )
            materiality_flag = materiality_service.variance_materiality(
                metric_code=metric_code,
                variance_abs=variance_abs.copy_abs(),
                variance_pct=variance_pct.copy_abs(),
                variance_bps=variance_bps.copy_abs(),
                rule_json=materiality_rule_json,
                entity_code=str(scope_json.get("entity", "") or "") or None,
            )
            output.append(
                ComputedVariance(
                    metric_code=metric_code,
                    comparison_type=definition.comparison_type,
                    base_period=base_period.isoformat() if base_period else None,
                    current_value=current_value,
                    baseline_value=baseline_value,
                    variance_abs=variance_abs,
                    variance_pct=variance_pct,
                    variance_bps=variance_bps,
                    days_change=days_change,
                    favorable_status=favorable,
                    materiality_flag=materiality_flag,
                    explanation_hint=(None if variance_abs == Decimal("0") else "review_required"),
                )
            )
        output.sort(key=lambda row: (row.metric_code, row.comparison_type))
        return output

    def _baseline(
        self,
        *,
        comparison_type: str,
        metric_code: str,
        current_value: Decimal,
        prior_series: list[tuple[date, Decimal]],
        scope_json: dict[str, Any],
    ) -> tuple[date | None, Decimal]:
        if comparison_type in {"mom_abs_pct", "basis_points_change", "days_change"}:
            if prior_series:
                period, value = prior_series[0]
                return period, q6(value)
            return None, Decimal("0")
        if comparison_type == "yoy_abs_pct":
            if len(prior_series) >= 12:
                period, value = prior_series[11]
                return period, q6(value)
            return None, Decimal("0")
        if comparison_type == "actual_vs_budget_abs_pct":
            budget = (scope_json.get("budget_metric_values") or {}).get(metric_code, "0")
            return None, q6(budget)
        if comparison_type == "actual_vs_forecast_abs_pct":
            forecast = (scope_json.get("forecast_metric_values") or {}).get(metric_code, "0")
            return None, q6(forecast)
        return None, Decimal("0")

    def _pct(self, *, current_value: Decimal, baseline_value: Decimal) -> Decimal:
        if baseline_value == Decimal("0"):
            return Decimal("0") if current_value == Decimal("0") else Decimal("100")
        return q6(((current_value - baseline_value) / baseline_value.copy_abs()) * Decimal("100"))
