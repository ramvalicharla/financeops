"""
Display scale utilities for FinanceOps.

IMPORTANT: These functions are for PRESENTATION ONLY.
All financial amounts are stored as full Decimal values.
Scaling is never applied to stored data.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Any


class DisplayScale(str, Enum):
    INR = "INR"
    LAKHS = "LAKHS"
    CRORES = "CRORES"
    THOUSANDS = "THOUSANDS"
    MILLIONS = "MILLIONS"
    BILLIONS = "BILLIONS"


SCALE_DIVISORS: dict[DisplayScale, Decimal] = {
    DisplayScale.INR: Decimal("1"),
    DisplayScale.LAKHS: Decimal("100000"),
    DisplayScale.CRORES: Decimal("10000000"),
    DisplayScale.THOUSANDS: Decimal("1000"),
    DisplayScale.MILLIONS: Decimal("1000000"),
    DisplayScale.BILLIONS: Decimal("1000000000"),
}

SCALE_LABELS: dict[DisplayScale, str] = {
    DisplayScale.INR: "₹",
    DisplayScale.LAKHS: "L",
    DisplayScale.CRORES: "Cr",
    DisplayScale.THOUSANDS: "K",
    DisplayScale.MILLIONS: "M",
    DisplayScale.BILLIONS: "B",
}

SCALE_FULL_LABELS: dict[DisplayScale, str] = {
    DisplayScale.INR: "in ₹",
    DisplayScale.LAKHS: "₹ in Lakhs",
    DisplayScale.CRORES: "₹ in Crores",
    DisplayScale.THOUSANDS: "in Thousands",
    DisplayScale.MILLIONS: "in Millions",
    DisplayScale.BILLIONS: "in Billions",
}

SCALE_DECIMAL_PLACES: dict[DisplayScale, int] = {
    DisplayScale.INR: 2,
    DisplayScale.LAKHS: 2,
    DisplayScale.CRORES: 2,
    DisplayScale.THOUSANDS: 2,
    DisplayScale.MILLIONS: 2,
    DisplayScale.BILLIONS: 3,
}


def _quantizer_for_scale(scale: DisplayScale) -> Decimal:
    places = SCALE_DECIMAL_PLACES[scale]
    if places <= 0:
        return Decimal("1")
    return Decimal("0." + ("0" * places))


def scale_amount(amount: Decimal, scale: DisplayScale) -> Decimal:
    divisor = SCALE_DIVISORS[scale]
    return (amount / divisor).quantize(
        _quantizer_for_scale(scale),
        rounding=ROUND_HALF_UP,
    )


def _format_indian_number(amount: Decimal) -> str:
    str_amount = f"{amount:.2f}"
    if "." in str_amount:
        integer_part, decimal_part = str_amount.split(".")
    else:
        integer_part, decimal_part = str_amount, "00"

    negative = integer_part.startswith("-")
    if negative:
        integer_part = integer_part[1:]

    if len(integer_part) <= 3:
        formatted = integer_part
    else:
        result = integer_part[-3:]
        remaining = integer_part[:-3]
        while remaining:
            result = remaining[-2:] + "," + result
            remaining = remaining[:-2]
        formatted = result

    output = f"{formatted}.{decimal_part}"
    if negative:
        return f"-{output}"
    return output


def format_scaled_amount(
    amount: Decimal,
    scale: DisplayScale,
    currency_symbol: str = "₹",
    show_label: bool = True,
) -> str:
    scaled = scale_amount(amount, scale)
    label = SCALE_LABELS[scale] if show_label else ""
    if scale == DisplayScale.INR:
        return f"{currency_symbol}{_format_indian_number(scaled)}"
    decimals = SCALE_DECIMAL_PLACES[scale]
    return f"{currency_symbol}{scaled:,.{decimals}f}{label}"


def get_effective_scale(user_override: str | None, tenant_default: str | None) -> DisplayScale:
    raw = user_override or tenant_default or DisplayScale.LAKHS.value
    try:
        return DisplayScale(raw)
    except ValueError:
        return DisplayScale.LAKHS


def scale_report_data(data: dict[str, Any], amount_keys: list[str], scale: DisplayScale) -> dict[str, Any]:
    result = dict(data)
    for key in amount_keys:
        if key in result and result[key] is not None:
            result[key] = scale_amount(Decimal(str(result[key])), scale)
    result["_display_scale"] = scale.value
    result["_scale_label"] = SCALE_FULL_LABELS[scale]
    return result


__all__ = [
    "DisplayScale",
    "SCALE_DIVISORS",
    "SCALE_LABELS",
    "SCALE_FULL_LABELS",
    "SCALE_DECIMAL_PLACES",
    "scale_amount",
    "format_scaled_amount",
    "get_effective_scale",
    "scale_report_data",
    "_format_indian_number",
]

