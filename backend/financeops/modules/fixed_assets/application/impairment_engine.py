from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

_QUANT = Decimal("0.0001")


def _q4(value: Decimal) -> Decimal:
    return Decimal(str(value)).quantize(_QUANT, rounding=ROUND_HALF_UP)


def calculate_value_in_use(
    cash_flows: list[Decimal],
    discount_rate: Decimal,
    terminal_growth_rate: Decimal = Decimal("0.03"),
) -> Decimal:
    if not cash_flows:
        return Decimal("0.0000")

    rate = Decimal(str(discount_rate))
    growth = Decimal(str(terminal_growth_rate))
    discounted = Decimal("0")
    for idx, cash_flow in enumerate(cash_flows, start=1):
        factor = (Decimal("1") + rate) ** idx
        discounted += Decimal(str(cash_flow)) / factor

    last_cf = Decimal(str(cash_flows[-1]))
    if rate > growth:
        terminal = (last_cf * (Decimal("1") + growth)) / (rate - growth)
        terminal_factor = (Decimal("1") + rate) ** len(cash_flows)
        discounted += terminal / terminal_factor

    return _q4(discounted)


def calculate_recoverable_amount(
    value_in_use: Decimal,
    fvlcts: Decimal,
) -> Decimal:
    return max(Decimal(str(value_in_use)), Decimal(str(fvlcts)))


def calculate_impairment_loss(
    nbv: Decimal,
    recoverable_amount: Decimal,
) -> Decimal:
    loss = Decimal(str(nbv)) - Decimal(str(recoverable_amount))
    return max(_q4(loss), Decimal("0"))


__all__ = [
    "calculate_value_in_use",
    "calculate_recoverable_amount",
    "calculate_impairment_loss",
]
