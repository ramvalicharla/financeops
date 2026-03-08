from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from statistics import fmean

from financeops.modules.anomaly_pattern_engine.domain.enums import SeverityLevel

SIX_DP = Decimal("0.000001")
ONE = Decimal("1")
ZERO = Decimal("0")

SEVERITY_RANK = {
    SeverityLevel.INFO.value: 0,
    SeverityLevel.LOW.value: 1,
    SeverityLevel.MEDIUM.value: 2,
    SeverityLevel.HIGH.value: 3,
    SeverityLevel.CRITICAL.value: 4,
}


def q6(value: Decimal | int | float | str) -> Decimal:
    return Decimal(str(value)).quantize(SIX_DP, rounding=ROUND_HALF_UP)


def clamp01(value: Decimal) -> Decimal:
    if value < ZERO:
        return ZERO
    if value > ONE:
        return ONE
    return q6(value)


def decimal_mean(values: list[Decimal]) -> Decimal:
    if not values:
        return ZERO
    return q6(fmean(values))


def decimal_std_pop(values: list[Decimal]) -> Decimal:
    if len(values) < 2:
        return ZERO
    mean = decimal_mean(values)
    variance = sum((value - mean) ** 2 for value in values) / Decimal(len(values))
    return q6(variance.sqrt())


def severity_rank(value: str) -> int:
    return SEVERITY_RANK.get(value, 0)
