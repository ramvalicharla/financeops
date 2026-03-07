from __future__ import annotations

from decimal import Decimal
from typing import Any

from financeops.modules.financial_risk_engine.domain.enums import SeverityLevel
from financeops.modules.financial_risk_engine.domain.invariants import clamp01, q6


class MaterialityService:
    def merged_rule_json(self, rows: list[Any]) -> dict[str, Any]:
        merged: dict[str, Any] = {
            "materiality_threshold": "0.2",
            "severity_thresholds": {
                "critical": "0.85",
                "high": "0.65",
                "medium": "0.40",
                "low": "0.20",
            },
        }
        for row in sorted(rows, key=lambda item: (item.rule_code, item.effective_from, str(item.id))):
            merged.update(row.threshold_json or {})
            if row.severity_mapping_json:
                merged["severity_thresholds"] = {
                    **merged.get("severity_thresholds", {}),
                    **row.severity_mapping_json,
                }
        return merged

    def severity_for_score(self, *, score: Decimal, rule_json: dict[str, Any]) -> SeverityLevel:
        score = clamp01(score)
        thresholds = rule_json.get("severity_thresholds", {})
        critical = Decimal(str(thresholds.get("critical", "0.85")))
        high = Decimal(str(thresholds.get("high", "0.65")))
        medium = Decimal(str(thresholds.get("medium", "0.40")))
        low = Decimal(str(thresholds.get("low", "0.20")))
        if score >= critical:
            return SeverityLevel.CRITICAL
        if score >= high:
            return SeverityLevel.HIGH
        if score >= medium:
            return SeverityLevel.MEDIUM
        if score >= low:
            return SeverityLevel.LOW
        return SeverityLevel.INFO

    def materiality_flag(self, *, score: Decimal, rule_json: dict[str, Any]) -> bool:
        threshold = Decimal(str(rule_json.get("materiality_threshold", "0.2")))
        return q6(score) >= q6(threshold)
