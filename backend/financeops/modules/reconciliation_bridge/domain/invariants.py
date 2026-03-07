from __future__ import annotations

from decimal import Decimal

SCALE_6 = Decimal("0.000001")


def assert_variance_invariant(
    *,
    source_a_value: Decimal,
    source_b_value: Decimal,
    variance_value: Decimal,
) -> None:
    if source_a_value - source_b_value != variance_value:
        raise ValueError("variance invariant violated")
