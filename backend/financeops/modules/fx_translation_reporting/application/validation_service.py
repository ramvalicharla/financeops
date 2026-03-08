from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import Any


class ValidationService:
    def validate_source_run_refs(self, *, source_run_refs: Sequence[dict[str, Any]]) -> None:
        if not source_run_refs:
            raise ValueError("source_consolidation_run_refs cannot be empty")
        seen: set[str] = set()
        for row in source_run_refs:
            source_type = str(row.get("source_type", "")).strip()
            run_id = str(row.get("run_id", "")).strip()
            if not source_type or not run_id:
                raise ValueError("source_run_refs rows must include source_type and run_id")
            key = f"{source_type}:{run_id}"
            if key in seen:
                raise ValueError("duplicate source_run_refs rows are not allowed")
            seen.add(key)

    def validate_active_definition_sets(
        self,
        *,
        reporting_currency_rows: Sequence[object],
        translation_rule_rows: Sequence[object],
        rate_policy_rows: Sequence[object],
        reporting_period: date,
    ) -> None:
        if not reporting_currency_rows:
            raise ValueError(
                f"No active reporting currency definition found for period {reporting_period.isoformat()}"
            )
        if not translation_rule_rows:
            raise ValueError(
                f"No active FX translation rule found for period {reporting_period.isoformat()}"
            )
        if not rate_policy_rows:
            raise ValueError(
                f"No active FX rate selection policy found for period {reporting_period.isoformat()}"
            )

