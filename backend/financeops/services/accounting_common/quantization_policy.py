from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

_RATE_QUANT = Decimal("0.000001")
_PERSISTED_AMOUNT_QUANT = Decimal("0.000001")
_OUTPUT_AMOUNT_QUANT = Decimal("0.01")


def _to_decimal(value: Decimal | str | int | float) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def quantize_rate(value: Decimal | str | int | float) -> Decimal:
    return _to_decimal(value).quantize(_RATE_QUANT, rounding=ROUND_HALF_UP)


def quantize_persisted_amount(value: Decimal | str | int | float) -> Decimal:
    return _to_decimal(value).quantize(_PERSISTED_AMOUNT_QUANT, rounding=ROUND_HALF_UP)


def quantize_output_amount(value: Decimal | str | int | float) -> Decimal:
    return _to_decimal(value).quantize(_OUTPUT_AMOUNT_QUANT, rounding=ROUND_HALF_UP)


def quantize_mapping_values(payload: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in payload.items():
        if isinstance(value, Decimal):
            result[key] = quantize_persisted_amount(value)
        else:
            result[key] = value
    return result
