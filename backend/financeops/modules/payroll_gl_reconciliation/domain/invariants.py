from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

SIX_DP = Decimal("0.000001")
HUNDRED = Decimal("100")


def q6(value: Decimal | int | float | str) -> Decimal:
    return Decimal(str(value)).quantize(SIX_DP, rounding=ROUND_HALF_UP)


def assert_variance(*, payroll_value: Decimal, gl_value: Decimal, variance_value: Decimal) -> None:
    if q6(payroll_value - gl_value) != q6(variance_value):
        raise ValueError("payroll-gl variance invariant violated")

