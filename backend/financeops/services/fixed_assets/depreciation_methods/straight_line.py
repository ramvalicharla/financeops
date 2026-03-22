from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from financeops.services.accounting_common.quantization_policy import quantize_persisted_amount


@dataclass(frozen=True)
class StraightLineRow:
    period_seq: int
    period_start: date
    period_end: date
    depreciation_date: date
    depreciation_amount_reporting_currency: Decimal


def _days_in_month(value: date) -> int:
    return calendar.monthrange(value.year, value.month)[1]


def _eligible_days(period_start: date, period_end: date) -> int:
    return (period_end - period_start).days + 1


def compute_straight_line_rows(
    *,
    opening_carrying_amount_reporting_currency: Decimal,
    residual_value_reporting_currency: Decimal,
    useful_life_months: int,
    periods: list[tuple[int, date, date, date]],
) -> list[StraightLineRow]:
    if useful_life_months <= 0:
        return []

    depreciable_base = quantize_persisted_amount(
        opening_carrying_amount_reporting_currency - residual_value_reporting_currency
    )
    if depreciable_base <= Decimal("0.000000"):
        return []

    monthly_full = depreciable_base / Decimal(str(useful_life_months))
    rows: list[StraightLineRow] = []

    allocated = Decimal("0")
    for period_seq, period_start, period_end, depreciation_date in periods:
        days = _eligible_days(period_start, period_end)
        denominator = _days_in_month(depreciation_date)
        factor = Decimal(str(days)) / Decimal(str(denominator))
        raw_amount = monthly_full * factor
        amount = quantize_persisted_amount(raw_amount)
        allocated = quantize_persisted_amount(allocated + amount)
        rows.append(
            StraightLineRow(
                period_seq=period_seq,
                period_start=period_start,
                period_end=period_end,
                depreciation_date=depreciation_date,
                depreciation_amount_reporting_currency=amount,
            )
        )

    residual = quantize_persisted_amount(depreciable_base - allocated)
    if rows and residual != Decimal("0.000000"):
        last = rows[-1]
        adjusted = quantize_persisted_amount(last.depreciation_amount_reporting_currency + residual)
        rows[-1] = StraightLineRow(
            period_seq=last.period_seq,
            period_start=last.period_start,
            period_end=last.period_end,
            depreciation_date=last.depreciation_date,
            depreciation_amount_reporting_currency=max(adjusted, Decimal("0.000000")),
        )

    return rows

