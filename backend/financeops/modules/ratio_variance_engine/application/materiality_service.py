from __future__ import annotations

from decimal import Decimal
from typing import Any

from financeops.modules.ratio_variance_engine.domain.enums import FavorableStatus
from financeops.modules.ratio_variance_engine.domain.invariants import (
    q6,
)
from financeops.modules.ratio_variance_engine.domain.value_objects import (
    DefinitionVersionTokenInput,
)
from financeops.modules.ratio_variance_engine.infrastructure.token_builder import (
    build_definition_version_token,
)


class MaterialityService:
    def version_token(self, rules: list[Any]) -> str:
        rows = [
            {
                "definition_code": str(getattr(item, "definition_code", "")),
                "rule_json": dict(getattr(item, "rule_json", {}) or {}),
                "effective_from": getattr(item, "effective_from").isoformat(),
                "status": str(getattr(item, "status", "")),
            }
            for item in sorted(
                rules,
                key=lambda row: (
                    str(getattr(row, "definition_code", "")),
                    getattr(row, "effective_from", None),
                    str(getattr(row, "id", "")),
                ),
            )
        ]
        return build_definition_version_token(DefinitionVersionTokenInput(rows=rows))

    def merged_rule_json(self, rules: list[Any]) -> dict[str, Any]:
        merged: dict[str, Any] = {
            "absolute_threshold": "0",
            "percentage_threshold": "0",
            "basis_points_threshold": "0",
            "always_material_metrics": [],
            "metric_overrides": {},
            "entity_overrides": {},
        }
        for rule in sorted(
            rules,
            key=lambda item: (
                str(getattr(item, "definition_code", "")),
                getattr(item, "effective_from", None),
                str(getattr(item, "id", "")),
            ),
        ):
            payload = dict(getattr(rule, "rule_json", {}) or {})
            merged.update(payload)
        return merged

    def metric_materiality(
        self,
        *,
        metric_code: str,
        value: Decimal,
        rule_json: dict[str, Any],
        entity_code: str | None = None,
    ) -> bool:
        abs_threshold = q6(rule_json.get("absolute_threshold", "0"))
        metric_overrides = rule_json.get("metric_overrides") or {}
        entity_overrides = rule_json.get("entity_overrides") or {}
        always = {str(item) for item in (rule_json.get("always_material_metrics") or [])}
        if metric_code in always and q6(value.copy_abs()) > Decimal("0"):
            return True
        metric_override = metric_overrides.get(metric_code)
        if isinstance(metric_override, dict) and "absolute_threshold" in metric_override:
            abs_threshold = q6(metric_override["absolute_threshold"])
        if entity_code:
            entity_override = entity_overrides.get(entity_code)
            if isinstance(entity_override, dict) and "absolute_threshold" in entity_override:
                abs_threshold = q6(entity_override["absolute_threshold"])
        return q6(value.copy_abs()) > abs_threshold

    def variance_materiality(
        self,
        *,
        metric_code: str,
        variance_abs: Decimal,
        variance_pct: Decimal,
        variance_bps: Decimal,
        rule_json: dict[str, Any],
        entity_code: str | None = None,
    ) -> bool:
        abs_threshold = q6(rule_json.get("absolute_threshold", "0"))
        pct_threshold = q6(rule_json.get("percentage_threshold", "0"))
        bps_threshold = q6(rule_json.get("basis_points_threshold", "0"))
        metric_overrides = rule_json.get("metric_overrides") or {}
        entity_overrides = rule_json.get("entity_overrides") or {}
        always = {str(item) for item in (rule_json.get("always_material_metrics") or [])}
        if metric_code in always and q6(variance_abs) > Decimal("0"):
            return True
        metric_override = metric_overrides.get(metric_code)
        if isinstance(metric_override, dict):
            if "absolute_threshold" in metric_override:
                abs_threshold = q6(metric_override["absolute_threshold"])
            if "percentage_threshold" in metric_override:
                pct_threshold = q6(metric_override["percentage_threshold"])
            if "basis_points_threshold" in metric_override:
                bps_threshold = q6(metric_override["basis_points_threshold"])
        if entity_code:
            entity_override = entity_overrides.get(entity_code)
            if isinstance(entity_override, dict):
                if "absolute_threshold" in entity_override:
                    abs_threshold = q6(entity_override["absolute_threshold"])
                if "percentage_threshold" in entity_override:
                    pct_threshold = q6(entity_override["percentage_threshold"])
                if "basis_points_threshold" in entity_override:
                    bps_threshold = q6(entity_override["basis_points_threshold"])

        pct_value = q6(variance_pct.copy_abs())
        bps_value = q6(variance_bps.copy_abs())
        return (
            q6(variance_abs.copy_abs()) > abs_threshold
            or pct_value > pct_threshold
            or bps_value > bps_threshold
        )

    def favorable_status(
        self,
        *,
        directionality: str,
        delta: Decimal,
    ) -> FavorableStatus:
        if directionality == "higher_is_better":
            if delta > Decimal("0"):
                return FavorableStatus.FAVORABLE
            if delta < Decimal("0"):
                return FavorableStatus.UNFAVORABLE
            return FavorableStatus.NEUTRAL
        if directionality == "lower_is_better":
            if delta < Decimal("0"):
                return FavorableStatus.FAVORABLE
            if delta > Decimal("0"):
                return FavorableStatus.UNFAVORABLE
            return FavorableStatus.NEUTRAL
        return FavorableStatus.NEUTRAL
