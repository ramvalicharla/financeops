from __future__ import annotations

from decimal import Decimal

from financeops.modules.anomaly_pattern_engine.domain.invariants import clamp01, q6


class ScoringService:
    def normalized_score_from_z(self, z_score: Decimal) -> Decimal:
        # Clamp |z| into [0, 1] by mapping 3-sigma to 1.
        return clamp01(q6(abs(z_score) / Decimal("3")))

    def confidence(
        self,
        *,
        has_metric_signals: bool,
        has_variance_signals: bool,
        has_trend_signals: bool,
        has_risk_signals: bool,
        has_open_reconciliation: bool,
    ) -> Decimal:
        score = Decimal("1")
        if not has_metric_signals:
            score -= Decimal("0.30")
        if not has_variance_signals:
            score -= Decimal("0.20")
        if not has_trend_signals:
            score -= Decimal("0.15")
        if not has_risk_signals:
            score -= Decimal("0.10")
        if has_open_reconciliation:
            score -= Decimal("0.20")
        return clamp01(q6(score))
