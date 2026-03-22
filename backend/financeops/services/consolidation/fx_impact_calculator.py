from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

RATE_PRECISION = Decimal("0.000001")
PERSISTED_AMOUNT_PRECISION = Decimal("0.000001")
OUTPUT_AMOUNT_PRECISION = Decimal("0.01")


def quantize_rate(value: Decimal) -> Decimal:
    return value.quantize(RATE_PRECISION, rounding=ROUND_HALF_UP)


def quantize_persisted_amount(value: Decimal) -> Decimal:
    return value.quantize(PERSISTED_AMOUNT_PRECISION, rounding=ROUND_HALF_UP)


def quantize_output_amount(value: Decimal) -> Decimal:
    return value.quantize(OUTPUT_AMOUNT_PRECISION, rounding=ROUND_HALF_UP)


def compute_fx_delta_component(
    *,
    parent_amount: Decimal,
    local_amount: Decimal,
    expected_rate: Decimal,
) -> Decimal:
    expected_parent = quantize_persisted_amount(local_amount * quantize_rate(expected_rate))
    return quantize_persisted_amount(parent_amount - expected_parent)

