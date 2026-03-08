from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP


def q6(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
