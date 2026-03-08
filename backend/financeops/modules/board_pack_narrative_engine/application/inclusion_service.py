from __future__ import annotations

from typing import Any


class InclusionService:
    def should_include_section(
        self,
        *,
        section_code: str,
        rules: list[Any],
        risk_count: int,
        anomaly_count: int,
    ) -> bool:
        decision = True
        for rule in sorted(rules, key=lambda item: (item.rule_code, item.id)):
            logic = rule.inclusion_logic_json or {}
            section_codes = set(logic.get("section_codes", []))
            if section_codes and section_code not in section_codes:
                continue
            min_risk = int(logic.get("min_risk_count", 0))
            min_anomaly = int(logic.get("min_anomaly_count", 0))
            if risk_count < min_risk or anomaly_count < min_anomaly:
                decision = False
        return decision

    def top_limit(self, *, rules: list[Any], default: int = 5) -> int:
        limit = default
        for rule in sorted(rules, key=lambda item: (item.rule_code, item.id)):
            logic = rule.inclusion_logic_json or {}
            if "top_limit" in logic:
                limit = max(1, int(logic["top_limit"]))
        return limit
