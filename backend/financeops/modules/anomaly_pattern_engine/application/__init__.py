from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any


class ValidationService:
    def validate_run_inputs(
        self,
        *,
        source_metric_run_ids: list[uuid.UUID],
        source_variance_run_ids: list[uuid.UUID],
        source_trend_run_ids: list[uuid.UUID],
        source_risk_run_ids: list[uuid.UUID],
        source_reconciliation_session_ids: list[uuid.UUID],
    ) -> None:
        if not source_metric_run_ids:
            raise ValueError("At least one metric run is required")
        if not source_variance_run_ids:
            raise ValueError("At least one variance run is required")
        self._assert_unique(source_metric_run_ids, "metric run")
        self._assert_unique(source_variance_run_ids, "variance run")
        self._assert_unique(source_trend_run_ids, "trend run")
        self._assert_unique(source_risk_run_ids, "risk run")
        self._assert_unique(source_reconciliation_session_ids, "reconciliation session")

    def validate_definition_sets(
        self,
        *,
        definitions: list[Any],
        pattern_rules: list[Any],
        persistence_rules: list[Any],
        correlation_rules: list[Any],
        statistical_rules: list[Any],
    ) -> None:
        if not definitions:
            raise ValueError("No active anomaly definitions found")
        if not pattern_rules:
            raise ValueError("No active anomaly pattern rules found")
        if not persistence_rules:
            raise ValueError("No active anomaly persistence rules found")
        if not correlation_rules:
            raise ValueError("No active anomaly correlation rules found")
        if not statistical_rules:
            raise ValueError("No active anomaly statistical rules found")

    def validate_statistical_rule(self, *, rule: Any) -> None:
        if rule.rolling_window not in (3, 6, 12, 24):
            raise ValueError("Invalid statistical rolling_window")
        if Decimal(str(rule.z_threshold)) <= 0:
            raise ValueError("Invalid z-threshold")

    def _assert_unique(self, values: list[uuid.UUID], label: str) -> None:
        if len({str(value) for value in values}) != len(values):
            raise ValueError(f"Duplicate {label} references are not allowed")
