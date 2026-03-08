from __future__ import annotations

from decimal import Decimal
from typing import Any

from financeops.modules.cash_flow_engine.domain.invariants import q6


class BridgeService:
    def compute_derived_values(
        self,
        *,
        base_line_values: dict[str, Decimal],
        bridge_logic_json: dict[str, Any],
    ) -> dict[str, Decimal]:
        derived: dict[str, Decimal] = {}
        derived_rules = bridge_logic_json.get("derived_lines", [])
        if not isinstance(derived_rules, list):
            return derived

        ordered_rules = sorted(
            [
                rule
                for rule in derived_rules
                if isinstance(rule, dict) and str(rule.get("line_code", "")).strip()
            ],
            key=lambda rule: (
                int(rule.get("line_order", 10_000)),
                str(rule.get("line_code", "")),
            ),
        )
        all_known_values = {**base_line_values}
        for rule in ordered_rules:
            line_code = str(rule.get("line_code", "")).strip()
            components = rule.get("components", [])
            if not isinstance(components, list):
                continue
            total = Decimal("0")
            for component in components:
                if not isinstance(component, dict):
                    continue
                multiplier = Decimal(str(component.get("multiplier", "1")))
                constant_raw = component.get("constant_value")
                if constant_raw is not None:
                    total += q6(Decimal(str(constant_raw)) * multiplier)
                    continue
                ref_line = str(
                    component.get("line_code", component.get("ref_line_code", ""))
                ).strip()
                if not ref_line:
                    continue
                source_value = all_known_values.get(ref_line, Decimal("0"))
                total += q6(source_value * multiplier)
            derived[line_code] = q6(total)
            all_known_values[line_code] = q6(total)
        return derived
