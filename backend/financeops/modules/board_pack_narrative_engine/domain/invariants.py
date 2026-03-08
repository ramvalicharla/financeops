from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

SIX_DP = Decimal("0.000001")
ONE = Decimal("1")
ZERO = Decimal("0")


def q6(value: Decimal | int | float | str) -> Decimal:
    return Decimal(str(value)).quantize(SIX_DP, rounding=ROUND_HALF_UP)


def clamp01(value: Decimal) -> Decimal:
    if value < ZERO:
        return ZERO
    if value > ONE:
        return ONE
    return q6(value)
