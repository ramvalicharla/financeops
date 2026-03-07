from __future__ import annotations

from decimal import Decimal


SIX_DP = Decimal("0.000001")


def quantize_6dp(value: Decimal) -> Decimal:
    return value.quantize(SIX_DP)
