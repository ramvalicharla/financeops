from __future__ import annotations

from decimal import Decimal
from typing import Any

from financeops.modules.equity_engine.domain.invariants import q6


class MappingService:
    def _selector_metric_codes(self, mapping: Any) -> list[str]:
        selector = dict(mapping.source_selector_json or {})
        codes = selector.get("metric_codes") or []
        return sorted({str(code) for code in codes if str(code)})

    def phase_for_mapping(self, mapping: Any) -> str:
        transform = dict(mapping.transformation_logic_json or {})
        phase = str(transform.get("phase", "movement")).strip().lower()
        if phase not in {"opening", "movement"}:
            return "movement"
        return phase

    def sum_source_values(
        self,
        *,
        mapping: Any,
        consolidation_values: dict[str, Decimal],
        fx_values: dict[str, Decimal],
        ownership_values: dict[str, Decimal],
    ) -> Decimal:
        codes = self._selector_metric_codes(mapping)
        total = Decimal("0")
        if str(mapping.source_type) in {"consolidation_result", "pnl_result"}:
            for code in codes:
                total += consolidation_values.get(code, Decimal("0"))
        elif str(mapping.source_type) == "fx_translation_result":
            for code in codes:
                total += fx_values.get(code, Decimal("0"))
        elif str(mapping.source_type) == "ownership_result":
            for code in codes:
                total += ownership_values.get(code, Decimal("0"))
        return q6(total)
