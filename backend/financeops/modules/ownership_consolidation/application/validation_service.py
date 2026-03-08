from __future__ import annotations

import uuid
from collections.abc import Sequence
from decimal import Decimal
from typing import Any


class ValidationService:
    def validate_source_run_refs(self, *, source_consolidation_run_refs: Sequence[dict[str, Any]]) -> None:
        if not source_consolidation_run_refs:
            raise ValueError("At least one source consolidation run reference is required")
        seen: set[str] = set()
        for row in source_consolidation_run_refs:
            source_type = str(row.get("source_type", "")).strip()
            run_id = str(row.get("run_id", "")).strip()
            if not source_type or not run_id:
                raise ValueError("Each source run reference requires source_type and run_id")
            try:
                uuid.UUID(run_id)
            except ValueError as exc:
                raise ValueError(f"Invalid source run_id: {run_id}") from exc
            key = f"{source_type}:{run_id}"
            if key in seen:
                raise ValueError("Duplicate source consolidation run references are not allowed")
            seen.add(key)

    def validate_definition_sets(
        self,
        *,
        structure_rows: Sequence[object],
        ownership_rule_rows: Sequence[object],
        minority_rule_rows: Sequence[object],
    ) -> None:
        if not structure_rows:
            raise ValueError("No active ownership structure definition is available")
        if not ownership_rule_rows:
            raise ValueError("No active ownership consolidation rule definition is available")
        if not minority_rule_rows:
            raise ValueError("No active minority interest rule definition is available")

    def validate_relationships(self, *, rows: Sequence[object]) -> None:
        if not rows:
            raise ValueError("No active ownership relationships are available")

    def validate_percentage(self, *, value: Decimal) -> None:
        if value < Decimal("0") or value > Decimal("100"):
            raise ValueError("Ownership percentage must be between 0 and 100")
