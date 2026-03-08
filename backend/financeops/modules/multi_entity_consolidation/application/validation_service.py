from __future__ import annotations

import uuid
from collections.abc import Iterable


class ValidationService:
    def validate_source_run_refs(self, *, source_run_refs: list[dict]) -> None:
        if not source_run_refs:
            raise ValueError("At least one source run reference is required")
        for row in source_run_refs:
            if not isinstance(row, dict):
                raise ValueError("Source run reference must be an object")
            source_type = str(row.get("source_type", "")).strip()
            run_id = row.get("run_id")
            if not source_type or run_id is None:
                raise ValueError("Each source run reference requires source_type and run_id")
            try:
                uuid.UUID(str(run_id))
            except ValueError as exc:
                raise ValueError(f"Invalid source run_id: {run_id}") from exc

    def validate_definition_sets(
        self,
        *,
        hierarchy_rows: Iterable[object],
        scope_rows: Iterable[object],
        rule_rows: Iterable[object],
        intercompany_rows: Iterable[object],
        adjustment_rows: Iterable[object],
    ) -> None:
        if not list(hierarchy_rows):
            raise ValueError("No active hierarchy version available")
        if not list(scope_rows):
            raise ValueError("No active scope version available")
        if not list(rule_rows):
            raise ValueError("No active consolidation rule version available")
        if not list(intercompany_rows):
            raise ValueError("No active intercompany mapping rule version available")
        if not list(adjustment_rows):
            raise ValueError("No active adjustment definition version available")

