from __future__ import annotations

from decimal import Decimal
from typing import Any

from financeops.modules.financial_risk_engine.domain.invariants import clamp01, q6


class ScoringService:
    def metric_signal(self, value: Decimal, *, weight: Decimal) -> Decimal:
        # Normalizes absolute metric magnitude into a bounded risk signal.
        return clamp01(q6(abs(value) / Decimal("1000")) * weight)

    def variance_signal(self, value: Decimal, *, weight: Decimal) -> Decimal:
        return clamp01(q6(abs(value) / Decimal("100")) * weight)

    def trend_signal(self, value: Decimal, *, weight: Decimal) -> Decimal:
        return clamp01(q6(abs(value) / Decimal("100")) * weight)

    def reconciliation_signal(self, count_open: int, *, weight: Decimal) -> Decimal:
        return clamp01(q6(Decimal(count_open) / Decimal("10")) * weight)

    def combine(self, parts: list[Decimal]) -> Decimal:
        total = sum(parts, start=Decimal("0"))
        return clamp01(q6(total))

    def dependency_signal(
        self,
        *,
        parent_score: Decimal,
        propagation_factor: Decimal,
        cap_limit: Decimal,
    ) -> Decimal:
        raw = q6(parent_score) * q6(propagation_factor)
        if raw > cap_limit:
            raw = cap_limit
        return clamp01(q6(raw))

    def confidence(
        self,
        *,
        has_signals: bool,
        unresolved_dependency: bool,
        has_open_reconciliation: bool,
    ) -> Decimal:
        score = Decimal("1")
        if not has_signals:
            score -= Decimal("0.4")
        if unresolved_dependency:
            score -= Decimal("0.3")
        if has_open_reconciliation:
            score -= Decimal("0.2")
        return clamp01(q6(score))

    def board_attention(
        self,
        *,
        severity: str,
        risk_domain: str,
        board_override: bool,
    ) -> bool:
        if board_override:
            return True
        if severity not in ("high", "critical"):
            return False
        return risk_domain in {"liquidity", "leverage", "board_critical"}

    def base_weight_for_definition(self, *, risk_code: str, risk_domain: str, rows: list[Any]) -> Decimal:
        weight = Decimal("1")
        for row in rows:
            if row.risk_code not in ("*", risk_code):
                continue
            if row.scope_type == "global":
                weight *= row.weight_value
            elif row.scope_type == "domain" and row.scope_value == risk_domain:
                weight *= row.weight_value
            elif row.scope_type == "board_critical" and row.board_critical_override:
                weight *= row.weight_value
        return q6(weight)
