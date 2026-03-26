from __future__ import annotations

from decimal import Decimal

_VALID_METHODS = {
    "FULL_CONSOLIDATION",
    "EQUITY_METHOD",
    "PROPORTIONATE",
    "EXCLUDED",
}


class ConsolidationMethodService:
    def derive_method(
        self,
        ownership_pct: Decimal,
        entity_type: str,
        manual_override: str | None,
    ) -> str:
        if manual_override is not None and manual_override in _VALID_METHODS:
            return manual_override
        if entity_type == "JOINT_VENTURE":
            return "PROPORTIONATE"
        if ownership_pct > Decimal("50.0000"):
            return "FULL_CONSOLIDATION"
        if ownership_pct >= Decimal("20.0000"):
            return "EQUITY_METHOD"
        return "EXCLUDED"


__all__ = ["ConsolidationMethodService"]
