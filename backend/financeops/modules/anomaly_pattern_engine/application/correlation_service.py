from __future__ import annotations

from decimal import Decimal


class CorrelationService:
    def correlation_flag(
        self,
        *,
        signal_scores: list[Decimal],
        min_signal_count: int,
    ) -> bool:
        if min_signal_count <= 0:
            raise ValueError("Invalid correlation min_signal_count")
        strong = [score for score in signal_scores if abs(score) >= Decimal("0.50")]
        return len(strong) >= min_signal_count
