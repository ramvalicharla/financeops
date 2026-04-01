from __future__ import annotations

from decimal import Decimal

_SCALE = Decimal("0.0001")


def quantize_4(value: Decimal) -> Decimal:
    return value.quantize(_SCALE)


def compute_revaluation_delta(
    *,
    foreign_balance: Decimal,
    closing_rate: Decimal,
    historical_base_balance: Decimal,
) -> tuple[Decimal, Decimal]:
    revalued_base = quantize_4(foreign_balance * closing_rate)
    fx_difference = quantize_4(revalued_base - historical_base_balance)
    return revalued_base, fx_difference


def compute_translated_equity_and_cta(
    *,
    assets: Decimal,
    liabilities: Decimal,
    equity_total: Decimal,
    retained_earnings: Decimal,
    closing_rate: Decimal,
    average_rate: Decimal,
) -> tuple[Decimal, Decimal]:
    equity_ex_retained = quantize_4(equity_total - retained_earnings)
    translated_assets = quantize_4(assets * closing_rate)
    translated_liabilities = quantize_4(liabilities * closing_rate)
    translated_equity = quantize_4(
        (equity_ex_retained * closing_rate) + (retained_earnings * average_rate)
    )
    cta_amount = quantize_4(translated_assets - (translated_liabilities + translated_equity))
    return translated_equity, cta_amount
