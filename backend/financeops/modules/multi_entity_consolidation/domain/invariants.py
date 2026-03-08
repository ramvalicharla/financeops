from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

SIX_DP = Decimal("0.000001")


def q6(value: Decimal) -> Decimal:
    return value.quantize(SIX_DP, rounding=ROUND_HALF_UP)

