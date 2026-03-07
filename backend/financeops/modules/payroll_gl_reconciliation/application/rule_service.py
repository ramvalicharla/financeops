from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from decimal import Decimal
from typing import Any

from financeops.db.models.payroll_gl_reconciliation import PayrollGlReconciliationRule
from financeops.modules.payroll_gl_reconciliation.domain.value_objects import (
    RuleVersionTokenInput,
)
from financeops.modules.payroll_gl_reconciliation.infrastructure.token_builder import (
    build_rule_version_token,
)


class RuleService:
    def rule_version_token(self, rows: Iterable[PayrollGlReconciliationRule]) -> str:
        payload: list[dict[str, Any]] = []
        for row in rows:
            payload.append(
                {
                    "rule_code": row.rule_code,
                    "rule_type": row.rule_type,
                    "tolerance_json": row.tolerance_json or {},
                    "materiality_json": row.materiality_json or {},
                    "timing_window_json": row.timing_window_json or {},
                    "classification_behavior_json": row.classification_behavior_json or {},
                    "effective_from": row.effective_from.isoformat(),
                    "status": row.status,
                }
            )
        payload.sort(
            key=lambda item: (
                str(item["rule_code"]),
                str(item["rule_type"]),
                str(item["effective_from"]),
            )
        )
        return build_rule_version_token(RuleVersionTokenInput(rule_rows=payload))

    def validate_active_set(
        self,
        rows: Iterable[PayrollGlReconciliationRule],
        *,
        reporting_period: date,
    ) -> list[PayrollGlReconciliationRule]:
        selected = sorted(
            (
                row
                for row in rows
                if row.status == "active" and row.effective_from <= reporting_period
            ),
            key=lambda item: (item.rule_code, item.effective_from, str(item.id)),
        )
        if not selected:
            raise ValueError("No active payroll-gl reconciliation rules found")

        by_type: dict[str, list[PayrollGlReconciliationRule]] = {}
        for row in selected:
            by_type.setdefault(row.rule_type, []).append(row)
        duplicate_types = sorted(
            rule_type for rule_type, rule_rows in by_type.items() if len(rule_rows) > 1
        )
        if duplicate_types:
            raise ValueError(
                "Duplicate active payroll-gl rule types found: "
                + ", ".join(duplicate_types)
            )
        return selected

    def merged_materiality(self, rows: Iterable[PayrollGlReconciliationRule]) -> dict[str, Any]:
        merged: dict[str, Any] = {
            "absolute_threshold": "0",
            "percentage_threshold": "0",
            "metric_overrides": {},
            "entity_overrides": {},
            "statutory_metrics": [],
        }
        for row in rows:
            materiality = row.materiality_json or {}
            if "absolute_threshold" in materiality:
                merged["absolute_threshold"] = str(materiality["absolute_threshold"])
            if "percentage_threshold" in materiality:
                merged["percentage_threshold"] = str(materiality["percentage_threshold"])
            if isinstance(materiality.get("metric_overrides"), dict):
                merged["metric_overrides"] = {
                    **merged["metric_overrides"],
                    **materiality["metric_overrides"],
                }
            if isinstance(materiality.get("entity_overrides"), dict):
                merged["entity_overrides"] = {
                    **merged["entity_overrides"],
                    **materiality["entity_overrides"],
                }
            if isinstance(materiality.get("statutory_metrics"), list):
                merged["statutory_metrics"] = sorted(
                    {
                        *[str(item) for item in merged["statutory_metrics"]],
                        *[str(item) for item in materiality["statutory_metrics"]],
                    }
                )
        return merged

    def merged_tolerance(self, rows: Iterable[PayrollGlReconciliationRule]) -> dict[str, Decimal]:
        absolute = Decimal("0")
        percentage = Decimal("0")
        for row in rows:
            tolerance = row.tolerance_json or {}
            if "absolute_threshold" in tolerance:
                absolute = Decimal(str(tolerance["absolute_threshold"]))
            if "percentage_threshold" in tolerance:
                percentage = Decimal(str(tolerance["percentage_threshold"]))
        return {"absolute_threshold": absolute, "percentage_threshold": percentage}

    def max_timing_lag_days(self, rows: Iterable[PayrollGlReconciliationRule]) -> int:
        lag = 0
        for row in rows:
            timing = row.timing_window_json or {}
            if "max_lag_days" in timing:
                lag = max(lag, int(timing["max_lag_days"]))
        return lag

