from __future__ import annotations

from typing import Any


class ValidationService:
    def validate_definition_sets(
        self,
        *,
        statement_rows: list[Any],
        line_definition_rows: list[Any],
        rollforward_rule_rows: list[Any],
        source_mapping_rows: list[Any],
    ) -> None:
        if not statement_rows:
            raise ValueError("No active equity statement definition found")
        if not line_definition_rows:
            raise ValueError("No active equity line definitions found")
        if not rollforward_rule_rows:
            raise ValueError("No active equity rollforward rules found")
        if not source_mapping_rows:
            raise ValueError("No active equity source mappings found")

    def validate_run_sources(
        self,
        *,
        consolidation_required: bool,
        consolidation_present: bool,
        fx_required: bool,
        fx_present: bool,
        ownership_required: bool,
        ownership_present: bool,
    ) -> None:
        if consolidation_required and not consolidation_present:
            raise ValueError("Missing consolidation source run")
        if fx_required and not fx_present:
            raise ValueError("Missing FX translation run while CTA/FX mapping is active")
        if ownership_required and not ownership_present:
            raise ValueError("Missing ownership run while ownership mapping is active")

    def validate_line_count(self, *, line_count: int) -> None:
        if line_count <= 0:
            raise ValueError("No equity lines were produced")
