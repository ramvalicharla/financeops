from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

_VARIANCE_PRECISION = Decimal("0.000001")


@dataclass(frozen=True)
class FxVarianceBreakdown:
    expected_difference: Decimal
    actual_difference: Decimal
    fx_variance: Decimal


def compute_fx_variance(
    *,
    expected_difference: Decimal,
    actual_difference: Decimal,
) -> FxVarianceBreakdown:
    variance = (actual_difference - expected_difference).quantize(
        _VARIANCE_PRECISION, rounding=ROUND_HALF_UP
    )
    return FxVarianceBreakdown(
        expected_difference=expected_difference.quantize(
            _VARIANCE_PRECISION, rounding=ROUND_HALF_UP
        ),
        actual_difference=actual_difference.quantize(
            _VARIANCE_PRECISION, rounding=ROUND_HALF_UP
        ),
        fx_variance=variance,
    )
