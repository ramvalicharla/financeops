from __future__ import annotations

import uuid
from typing import Any


class ValidationService:
    def validate_run_inputs(
        self,
        *,
        source_metric_run_ids: list[uuid.UUID],
        source_variance_run_ids: list[uuid.UUID],
        source_trend_run_ids: list[uuid.UUID],
        source_reconciliation_session_ids: list[uuid.UUID],
    ) -> None:
        if not source_metric_run_ids:
            raise ValueError("At least one metric run is required")
        if not source_variance_run_ids:
            raise ValueError("At least one variance run is required")
        if len({str(value) for value in source_metric_run_ids}) != len(source_metric_run_ids):
            raise ValueError("Duplicate metric run references are not allowed")
        if len({str(value) for value in source_variance_run_ids}) != len(source_variance_run_ids):
            raise ValueError("Duplicate variance run references are not allowed")
        if len({str(value) for value in source_trend_run_ids}) != len(source_trend_run_ids):
            raise ValueError("Duplicate trend run references are not allowed")
        if len({str(value) for value in source_reconciliation_session_ids}) != len(
            source_reconciliation_session_ids
        ):
            raise ValueError("Duplicate reconciliation session references are not allowed")

    def validate_definition_sets(
        self,
        *,
        definitions: list[Any],
        weights: list[Any],
        materiality_rules: list[Any],
    ) -> None:
        if not definitions:
            raise ValueError("No active risk definitions found")
        if not materiality_rules:
            raise ValueError("No active risk materiality rules found")
        # Weight configuration is allowed to be empty; default weight=1 applies.

    def validate_dependency_rows(self, *, dependency_rows: list[Any]) -> None:
        for row in dependency_rows:
            if row.propagation_factor < 0:
                raise ValueError("Invalid propagation factor")
            if row.cap_limit < 0:
                raise ValueError("Invalid dependency cap limit")
