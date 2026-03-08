from __future__ import annotations

from decimal import Decimal
from statistics import median

from financeops.modules.anomaly_pattern_engine.domain.invariants import (
    decimal_mean,
    decimal_std_pop,
    q6,
)


class StatisticalService:
    def rolling_window(self, values: list[Decimal], *, window: int) -> list[Decimal]:
        if window <= 0:
            raise ValueError("Invalid rolling window")
        if not values:
            return []
        if len(values) <= window:
            return list(values)
        return list(values[-window:])

    def rolling_mean(self, values: list[Decimal], *, window: int) -> Decimal:
        return decimal_mean(self.rolling_window(values, window=window))

    def rolling_std(self, values: list[Decimal], *, window: int) -> Decimal:
        return decimal_std_pop(self.rolling_window(values, window=window))

    def rolling_median(self, values: list[Decimal], *, window: int) -> Decimal:
        sliced = self.rolling_window(values, window=window)
        if not sliced:
            return Decimal("0")
        return q6(Decimal(str(median(sliced))))

    def rolling_pct_change(self, values: list[Decimal], *, window: int) -> Decimal:
        sliced = self.rolling_window(values, window=window)
        if len(sliced) < 2:
            return Decimal("0")
        start = sliced[0]
        end = sliced[-1]
        if start == 0:
            return Decimal("0")
        return q6((end - start) / abs(start))

    def z_score(self, *, current_value: Decimal, baseline_mean: Decimal, baseline_std: Decimal) -> Decimal:
        if baseline_std == 0:
            raise ValueError("Zero std-dev baseline is not allowed")
        return q6((current_value - baseline_mean) / baseline_std)

    def regime_shift_flag(
        self,
        *,
        values: list[Decimal],
        window: int,
        threshold_pct: Decimal,
    ) -> bool:
        if len(values) < window * 2:
            return False
        previous = values[-(window * 2) : -window]
        current = values[-window:]
        prev_mean = decimal_mean(previous)
        curr_mean = decimal_mean(current)
        if prev_mean == 0:
            return abs(curr_mean) > 0
        deviation = abs((curr_mean - prev_mean) / abs(prev_mean))
        return deviation >= threshold_pct
