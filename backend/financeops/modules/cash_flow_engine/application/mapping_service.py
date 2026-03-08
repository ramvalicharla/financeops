from __future__ import annotations

from decimal import Decimal
from typing import Any

from financeops.modules.cash_flow_engine.domain.invariants import q6


class MappingService:
    def mapping_applicable(
        self,
        *,
        ownership_applicability: str,
        fx_applicability: str,
        has_ownership_source: bool,
        has_fx_source: bool,
    ) -> bool:
        ownership_ok = True
        if ownership_applicability == "ownership_only":
            ownership_ok = has_ownership_source
        elif ownership_applicability == "non_ownership_only":
            ownership_ok = not has_ownership_source

        fx_ok = True
        if fx_applicability == "fx_only":
            fx_ok = has_fx_source
        elif fx_applicability == "non_fx_only":
            fx_ok = not has_fx_source
        return ownership_ok and fx_ok

    def filter_applicable_mappings(
        self,
        *,
        mappings: list[Any],
        has_ownership_source: bool,
        has_fx_source: bool,
    ) -> list[Any]:
        return [
            row
            for row in mappings
            if self.mapping_applicable(
                ownership_applicability=str(row.ownership_applicability),
                fx_applicability=str(row.fx_applicability),
                has_ownership_source=has_ownership_source,
                has_fx_source=has_fx_source,
            )
        ]

    def compute_line_value(
        self, *, source_value: Decimal, sign_multiplier: Decimal
    ) -> Decimal:
        return q6(q6(source_value) * q6(sign_multiplier))
