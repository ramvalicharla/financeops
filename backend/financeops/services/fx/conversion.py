from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from financeops.services.fx.normalization import normalize_rate_decimal

_CURRENCY_AMOUNT_PRECISION = Decimal("0.01")


@dataclass(frozen=True)
class ConvertedLine:
    reference: str | None
    amount: Decimal
    converted_amount: Decimal
    applied_rate: Decimal


def convert_amount(amount: Decimal, rate: Decimal) -> Decimal:
    normalized_rate = normalize_rate_decimal(rate)
    converted = amount * normalized_rate
    return converted.quantize(_CURRENCY_AMOUNT_PRECISION, rounding=ROUND_HALF_UP)


def apply_rate_to_lines(
    *,
    line_items: list[tuple[str | None, Decimal]],
    rate: Decimal,
) -> list[ConvertedLine]:
    normalized_rate = normalize_rate_decimal(rate)
    return [
        ConvertedLine(
            reference=reference,
            amount=amount,
            converted_amount=convert_amount(amount, normalized_rate),
            applied_rate=normalized_rate,
        )
        for reference, amount in line_items
    ]
