from __future__ import annotations

import calendar
import math
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from financeops.services.accounting_common.quantization_policy import quantize_persisted_amount, quantize_rate


@dataclass(frozen=True)
class ReducingBalanceRow:
    period_seq: int
    period_start: date
    period_end: date
    depreciation_date: date
    depreciation_amount_reporting_currency: Decimal


def reducing_balance_monthly_rate(annual_rate: Decimal) -> Decimal:
    annual = float(annual_rate)
    monthly = 1.0 - math.pow(1.0 - annual, 1.0 / 12.0)
    return quantize_rate(Decimal(str(monthly)))


def _days_in_month(value: date) -> int:
    return calendar.monthrange(value.year, value.month)[1]


def _eligible_days(period_start: date, period_end: date) -> int:
    return (period_end - period_start).days + 1


def compute_reducing_balance_rows(
    *,
    opening_carrying_amount_reporting_currency: Decimal,
    residual_value_reporting_currency: Decimal,
    annual_rate: Decimal,
    periods: list[tuple[int, date, date, date]],
) -> list[ReducingBalanceRow]:
    monthly_rate = reducing_balance_monthly_rate(annual_rate)
    opening = quantize_persisted_amount(opening_carrying_amount_reporting_currency)
    residual = quantize_persisted_amount(residual_value_reporting_currency)
    if opening <= residual:
        return []

    rows: list[ReducingBalanceRow] = []
    for period_seq, period_start, period_end, depreciation_date in periods:
        if opening <= residual:
            break

        full_amount = opening * monthly_rate
        days = _eligible_days(period_start, period_end)
        denominator = _days_in_month(depreciation_date)
        factor = Decimal(str(days)) / Decimal(str(denominator))
        amount = quantize_persisted_amount(full_amount * factor)
        max_allowed = quantize_persisted_amount(opening - residual)
        if amount > max_allowed:
            amount = max_allowed
        if amount < Decimal("0.000000"):
            amount = Decimal("0.000000")

        rows.append(
            ReducingBalanceRow(
                period_seq=period_seq,
                period_start=period_start,
                period_end=period_end,
                depreciation_date=depreciation_date,
                depreciation_amount_reporting_currency=amount,
            )
        )
        opening = quantize_persisted_amount(opening - amount)

    return rows
