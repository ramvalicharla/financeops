from __future__ import annotations

from decimal import Decimal
from typing import Any

from financeops.modules.anomaly_pattern_engine.domain.enums import SeverityLevel
from financeops.modules.anomaly_pattern_engine.domain.invariants import q6


class MaterialityService:
    def merged_thresholds(self, rows: list[Any]) -> dict[str, Decimal]:
        thresholds = {
            "moderate_z": Decimal("1.5"),
            "high_z": Decimal("2.0"),
            "extreme_z": Decimal("3.0"),
            "material_score": Decimal("0.50"),
        }
        for row in sorted(rows, key=lambda item: (item.rule_code, item.effective_from, str(item.id))):
            cfg = row.configuration_json or {}
            if "moderate_z" in cfg:
                thresholds["moderate_z"] = Decimal(str(cfg["moderate_z"]))
            if "high_z" in cfg:
                thresholds["high_z"] = Decimal(str(cfg["high_z"]))
            if "extreme_z" in cfg:
                thresholds["extreme_z"] = Decimal(str(cfg["extreme_z"]))
            if "material_score" in cfg:
                thresholds["material_score"] = Decimal(str(cfg["material_score"]))
        return thresholds

    def severity_from_z(self, *, z_score: Decimal, thresholds: dict[str, Decimal]) -> SeverityLevel:
        z_abs = abs(q6(z_score))
        if z_abs >= thresholds["extreme_z"]:
            return SeverityLevel.CRITICAL
        if z_abs >= thresholds["high_z"]:
            return SeverityLevel.HIGH
        if z_abs >= thresholds["moderate_z"]:
            return SeverityLevel.MEDIUM
        if z_abs > Decimal("0"):
            return SeverityLevel.LOW
        return SeverityLevel.INFO

    def materiality_flag(self, *, anomaly_score: Decimal, thresholds: dict[str, Decimal]) -> bool:
        return q6(anomaly_score) >= thresholds["material_score"]

    def elevate_severity(
        self,
        *,
        current: SeverityLevel,
        risk_elevated: bool,
        materiality_elevated: bool,
        board_critical: bool,
    ) -> SeverityLevel:
        order = [
            SeverityLevel.INFO,
            SeverityLevel.LOW,
            SeverityLevel.MEDIUM,
            SeverityLevel.HIGH,
            SeverityLevel.CRITICAL,
        ]
        idx = order.index(current)
        if materiality_elevated:
            idx = max(idx, order.index(SeverityLevel.HIGH))
        if risk_elevated:
            idx = max(idx, order.index(SeverityLevel.HIGH))
        if board_critical:
            idx = max(idx, order.index(SeverityLevel.CRITICAL))
        return order[idx]
