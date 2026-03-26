from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from financeops.modules.prepaid_expenses.models import PrepaidSchedule

_QUANT = Decimal("0.0001")


@dataclass(slots=True)
class AmortisationPeriod:
    period_start: date
    period_end: date
    amount: Decimal
    is_last_period: bool


def _q4(value: Decimal) -> Decimal:
    return Decimal(str(value)).quantize(_QUANT, rounding=ROUND_HALF_UP)


def _month_end(value: date) -> date:
    next_month = value.replace(day=28) + timedelta(days=4)
    return next_month - timedelta(days=next_month.day)


def calculate_slm_schedule(
    total_amount: Decimal,
    coverage_start: date,
    coverage_end: date,
) -> list[AmortisationPeriod]:
    if coverage_end < coverage_start:
        return []

    total = Decimal(str(total_amount))
    total_days = Decimal((coverage_end - coverage_start).days + 1)
    periods: list[AmortisationPeriod] = []

    current_start = coverage_start
    allocated = Decimal("0")
    while current_start <= coverage_end:
        current_end = min(_month_end(current_start), coverage_end)
        days = Decimal((current_end - current_start).days + 1)
        amount = _q4(total * days / total_days)
        periods.append(
            AmortisationPeriod(
                period_start=current_start,
                period_end=current_end,
                amount=amount,
                is_last_period=False,
            )
        )
        allocated += amount
        current_start = current_end + timedelta(days=1)

    if periods:
        remainder = _q4(total - (allocated - periods[-1].amount))
        periods[-1].amount = remainder
        periods[-1].is_last_period = True

    return periods


def get_period_amount(
    schedule: PrepaidSchedule,
    period_start: date,
    period_end: date,
) -> Decimal:
    periods = calculate_slm_schedule(
        total_amount=Decimal(str(schedule.total_amount)),
        coverage_start=schedule.coverage_start,
        coverage_end=schedule.coverage_end,
    )
    total = Decimal("0")
    for item in periods:
        overlap_start = max(item.period_start, period_start)
        overlap_end = min(item.period_end, period_end)
        if overlap_end < overlap_start:
            continue
        if overlap_start == item.period_start and overlap_end == item.period_end:
            total += item.amount
            continue
        # Partial overlap fallback (rare): prorate period amount by overlapping days.
        overlap_days = Decimal((overlap_end - overlap_start).days + 1)
        period_days = Decimal((item.period_end - item.period_start).days + 1)
        total += _q4(item.amount * overlap_days / period_days)
    return _q4(total)


__all__ = ["AmortisationPeriod", "calculate_slm_schedule", "get_period_amount"]
