from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

SIX_DP = Decimal("0.000001")
HUNDRED = Decimal("100")
TEN_THOUSAND = Decimal("10000")


def q6(value: Decimal | int | float | str) -> Decimal:
    return Decimal(str(value)).quantize(SIX_DP, rounding=ROUND_HALF_UP)


def safe_div_pct(*, numerator: Decimal, denominator: Decimal) -> Decimal:
    if denominator == Decimal("0"):
        return Decimal("0") if numerator == Decimal("0") else HUNDRED
    return q6((numerator / denominator) * HUNDRED)


def assert_variance_invariant(*, current: Decimal, baseline: Decimal, variance_abs: Decimal) -> None:
    if q6(current - baseline) != q6(variance_abs):
        raise ValueError("variance invariant violated")
