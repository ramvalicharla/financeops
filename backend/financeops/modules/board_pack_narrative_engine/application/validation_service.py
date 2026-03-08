from __future__ import annotations

import uuid
from typing import Any


class ValidationService:
    def validate_run_inputs(
        self,
        *,
        source_metric_run_ids: list[uuid.UUID],
        source_risk_run_ids: list[uuid.UUID],
        source_anomaly_run_ids: list[uuid.UUID],
    ) -> None:
        if not source_metric_run_ids:
            raise ValueError("At least one metric run is required")
        if not source_risk_run_ids:
            raise ValueError("At least one risk run is required")
        if not source_anomaly_run_ids:
            raise ValueError("At least one anomaly run is required")
        self._assert_unique(source_metric_run_ids, "metric run")
        self._assert_unique(source_risk_run_ids, "risk run")
        self._assert_unique(source_anomaly_run_ids, "anomaly run")

    def validate_definition_sets(
        self,
        *,
        definitions: list[Any],
        sections: list[Any],
        templates: list[Any],
        inclusion_rules: list[Any],
    ) -> None:
        if not definitions:
            raise ValueError("No active board pack definitions found")
        if not sections:
            raise ValueError("No active board pack sections found")
        if not templates:
            raise ValueError("No active narrative templates found")
        if not inclusion_rules:
            raise ValueError("No active inclusion rules found")

    def _assert_unique(self, values: list[uuid.UUID], label: str) -> None:
        if len({str(value) for value in values}) != len(values):
            raise ValueError(f"Duplicate {label} references are not allowed")
