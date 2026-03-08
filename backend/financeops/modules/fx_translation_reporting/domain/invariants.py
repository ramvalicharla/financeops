from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

SIX_DP = Decimal("0.000001")
EIGHT_DP = Decimal("0.00000001")


def q6(value: Decimal) -> Decimal:
    return value.quantize(SIX_DP, rounding=ROUND_HALF_UP)


def q8(value: Decimal) -> Decimal:
    return value.quantize(EIGHT_DP, rounding=ROUND_HALF_UP)

