from __future__ import annotations

from decimal import Decimal
from typing import Any

from financeops.modules.equity_engine.domain.invariants import q6


class RollforwardService:
    def retained_earnings_movement(self, *, consolidation_values: dict[str, Decimal], rule: Any) -> Decimal:
        selector = dict(rule.source_selector_json or {})
        pnl_codes = selector.get("pnl_metric_codes") or selector.get("metric_codes") or []
        total = Decimal("0")
        for code in sorted({str(value) for value in pnl_codes if str(value)}):
            total += consolidation_values.get(code, Decimal("0"))
        return q6(total)

    def cta_movement(self, *, fx_rows: list[dict[str, Any]], rule: Any) -> Decimal:
        selector = dict(rule.source_selector_json or {})
        allowed = selector.get("metric_codes") or []
        allowed_codes = {str(code) for code in allowed if str(code)}
        total = Decimal("0")
        for row in fx_rows:
            metric_code = str(row.get("metric_code", ""))
            if allowed_codes and metric_code not in allowed_codes:
                continue
            translated = Decimal(str(row.get("translated_value", "0")))
            source = Decimal(str(row.get("source_value", "0")))
            total += translated - source
        return q6(total)

    def ownership_amount(self, *, ownership_values: dict[str, Decimal], metric_codes: list[str]) -> Decimal:
        total = Decimal("0")
        for code in sorted({str(value) for value in metric_codes if str(value)}):
            total += ownership_values.get(code, Decimal("0"))
        return q6(total)
