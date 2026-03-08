from __future__ import annotations

from collections.abc import Iterable


class ValidationService:
    def validate_definition_sets(
        self,
        *,
        statement_rows: list[object],
        line_mapping_rows: list[object],
        bridge_rule_rows: list[object],
    ) -> None:
        if not statement_rows:
            raise ValueError("No active cash flow statement definition found for period")
        if not line_mapping_rows:
            raise ValueError("No active cash flow line mapping found for period")
        if not bridge_rule_rows:
            raise ValueError("No active cash flow bridge rule found for period")

    def validate_source_refs(
        self,
        *,
        source_consolidation_run_ref: object,
    ) -> None:
        if source_consolidation_run_ref is None:
            raise ValueError("source_consolidation_run_ref is required")

    def validate_line_mappings_have_sources(
        self,
        *,
        missing_source_metrics: Iterable[str],
    ) -> None:
        missing = sorted({value for value in missing_source_metrics if value})
        if missing:
            raise ValueError(
                f"Missing source metrics for mappings: {', '.join(missing)}"
            )
