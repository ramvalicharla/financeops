from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Any

from financeops.db.models.ratio_variance_engine import MetricDefinition, MetricDefinitionComponent
from financeops.modules.ratio_variance_engine.application.materiality_service import (
    MaterialityService,
)
from financeops.modules.ratio_variance_engine.domain.entities import ComputedMetric
from financeops.modules.ratio_variance_engine.domain.enums import FavorableStatus
from financeops.modules.ratio_variance_engine.domain.invariants import q6, safe_div_pct
from financeops.modules.ratio_variance_engine.domain.value_objects import (
    DefinitionVersionTokenInput,
)
from financeops.modules.ratio_variance_engine.infrastructure.token_builder import (
    build_definition_version_token,
)


class MetricDefinitionService:
    def version_token(
        self,
        definitions: list[MetricDefinition],
        components_by_definition: dict[str, list[MetricDefinitionComponent]],
    ) -> str:
        rows: list[dict[str, Any]] = []
        for definition in sorted(definitions, key=lambda item: (item.definition_code, item.id)):
            components = components_by_definition.get(str(definition.id), [])
            rows.append(
                {
                    "definition_code": definition.definition_code,
                    "metric_code": definition.metric_code,
                    "formula_type": definition.formula_type,
                    "formula_json": definition.formula_json,
                    "unit_type": definition.unit_type,
                    "directionality": definition.directionality,
                    "effective_from": definition.effective_from.isoformat(),
                    "status": definition.status,
                    "components": [
                        {
                            "component_code": component.component_code,
                            "source_type": component.source_type,
                            "source_key": component.source_key,
                            "operator": component.operator,
                            "weight": str(component.weight),
                            "ordinal_position": component.ordinal_position,
                            "metadata_json": component.metadata_json,
                        }
                        for component in components
                    ],
                }
            )
        return build_definition_version_token(DefinitionVersionTokenInput(rows=rows))

    def compute_metrics(
        self,
        *,
        definitions: list[MetricDefinition],
        components_by_definition: dict[str, list[MetricDefinitionComponent]],
        source_values: dict[str, dict[str, Decimal]],
        rule_json: dict[str, Any],
        scope_json: dict[str, Any],
        materiality_service: MaterialityService,
    ) -> list[ComputedMetric]:
        metrics_by_code: dict[str, Decimal] = {}
        output: list[ComputedMetric] = []
        pending = sorted(definitions, key=lambda item: (item.definition_code, item.id))
        while pending:
            progressed = False
            next_pending: list[MetricDefinition] = []
            for definition in pending:
                components = components_by_definition.get(str(definition.id), [])
                try:
                    value = self._compute_value(
                        definition=definition,
                        components=components,
                        source_values=source_values,
                        metrics_by_code=metrics_by_code,
                    )
                except ValueError as exc:
                    if "Metric reference not resolved" in str(exc):
                        next_pending.append(definition)
                        continue
                    raise
                value = q6(value)
                metrics_by_code[definition.metric_code] = value
                output.append(
                    ComputedMetric(
                        metric_code=definition.metric_code,
                        unit_type=definition.unit_type,
                        dimension_json={
                            "scope": scope_json,
                            "definition_code": definition.definition_code,
                        },
                        metric_value=value,
                        favorable_status=FavorableStatus.NEUTRAL,
                        materiality_flag=materiality_service.metric_materiality(
                            metric_code=definition.metric_code,
                            value=value,
                            rule_json=rule_json,
                            entity_code=str(scope_json.get("entity", "") or "") or None,
                        ),
                        source_summary_json={
                            "formula_type": definition.formula_type,
                            "component_count": len(components),
                        },
                    )
                )
                progressed = True
            if not progressed and next_pending:
                unresolved = ", ".join(sorted(item.metric_code for item in next_pending))
                raise ValueError(
                    f"Unresolvable metric reference graph for definitions: {unresolved}"
                )
            pending = next_pending
        output.sort(key=lambda row: row.metric_code)
        return output

    def _compute_value(
        self,
        *,
        definition: MetricDefinition,
        components: list[MetricDefinitionComponent],
        source_values: dict[str, dict[str, Decimal]],
        metrics_by_code: dict[str, Decimal],
    ) -> Decimal:
        ordered = sorted(components, key=lambda item: (item.ordinal_position, item.id))
        if not ordered:
            return Decimal("0")

        resolved: list[Decimal] = []
        for component in ordered:
            base = self._resolve_component(
                component=component,
                source_values=source_values,
                metrics_by_code=metrics_by_code,
            )
            resolved.append(q6(base * Decimal(str(component.weight))))

        formula_type = definition.formula_type
        if formula_type == "ratio":
            numerator = resolved[0]
            denominator = resolved[1] if len(resolved) > 1 else Decimal("0")
            return safe_div_pct(numerator=numerator, denominator=denominator)
        if formula_type == "difference":
            left = resolved[0]
            right = resolved[1] if len(resolved) > 1 else Decimal("0")
            return q6(left - right)

        total = Decimal("0")
        for idx, component in enumerate(ordered):
            value = resolved[idx]
            operator = component.operator
            if idx == 0 and operator in {"none", "add"}:
                total = value
                continue
            if operator in {"add", "none"}:
                total = q6(total + value)
            elif operator == "subtract":
                total = q6(total - value)
            elif operator == "multiply":
                total = q6(total * value)
            elif operator == "divide":
                total = q6(total / value) if value != Decimal("0") else Decimal("0")
            else:
                raise ValueError(f"Unsupported metric component operator: {operator}")
        return q6(total)

    def _resolve_component(
        self,
        *,
        component: MetricDefinitionComponent,
        source_values: dict[str, dict[str, Decimal]],
        metrics_by_code: dict[str, Decimal],
    ) -> Decimal:
        source_type = component.source_type
        source_key = component.source_key
        if source_type == "metric_ref":
            if source_key not in metrics_by_code:
                raise ValueError(f"Metric reference not resolved: {source_key}")
            return metrics_by_code[source_key]
        if source_type == "constant":
            return q6(source_key)
        if source_type in {"mis_metric", "payroll_metric"}:
            return q6(source_values.get(source_type, {}).get(source_key, Decimal("0")))
        if source_type == "gl_account_prefix":
            total = Decimal("0")
            for account_code, value in source_values.get("gl_account_prefix", {}).items():
                if str(account_code).startswith(source_key):
                    total = q6(total + value)
            return q6(total)
        raise ValueError(f"Unsupported metric source_type: {source_type}")
