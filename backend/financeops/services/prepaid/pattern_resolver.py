from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from financeops.core.exceptions import ValidationError
from financeops.schemas.prepaid import (
    PrepaidInput,
    PrepaidPatternPeriodInput,
    PrepaidPatternType,
)
from financeops.services.accounting_common.quantization_policy import quantize_persisted_amount


@dataclass(frozen=True)
class NormalizedPatternPeriod:
    period_seq: int
    period_start_date: date
    period_end_date: date
    recognition_date: date
    weight: Decimal | None
    percentage: Decimal | None
    amount: Decimal | None


@dataclass(frozen=True)
class NormalizedPattern:
    pattern_type: PrepaidPatternType
    period_frequency: str
    periods: list[NormalizedPatternPeriod]
    canonical_json: dict[str, Any]


def _decimal_text(value: Decimal) -> str:
    return f"{quantize_persisted_amount(value):.6f}"


def _month_end(value: date) -> date:
    _, day = calendar.monthrange(value.year, value.month)
    return date(value.year, value.month, day)


def _validate_period_order(periods: list[PrepaidPatternPeriodInput], *, term_start: date, term_end: date) -> list[PrepaidPatternPeriodInput]:
    ordered = sorted(periods, key=lambda item: item.period_seq)
    expected = list(range(1, len(ordered) + 1))
    actual = [item.period_seq for item in ordered]
    if actual != expected:
        raise ValidationError("period_seq must be contiguous starting at 1")

    previous_end: date | None = None
    for item in ordered:
        if item.period_start_date < term_start or item.period_end_date > term_end:
            raise ValidationError("period range must stay within term range")
        if previous_end is not None and item.period_start_date != previous_end + timedelta(days=1):
            raise ValidationError("period ranges must be contiguous with no gaps or overlaps")
        previous_end = item.period_end_date

    if ordered[0].period_start_date != term_start:
        raise ValidationError("first period must start on term_start_date")
    if ordered[-1].period_end_date != term_end:
        raise ValidationError("last period must end on term_end_date")
    return ordered


def _normalize_straight_line_periods(*, term_start: date, term_end: date) -> list[NormalizedPatternPeriod]:
    periods: list[NormalizedPatternPeriod] = []
    cursor = term_start
    seq = 1
    while cursor <= term_end:
        end = min(_month_end(cursor), term_end)
        periods.append(
            NormalizedPatternPeriod(
                period_seq=seq,
                period_start_date=cursor,
                period_end_date=end,
                recognition_date=end,
                weight=None,
                percentage=None,
                amount=None,
            )
        )
        cursor = end + timedelta(days=1)
        seq += 1
    return periods


def _normalize_weighted_periods(periods: list[PrepaidPatternPeriodInput]) -> list[NormalizedPatternPeriod]:
    normalized: list[NormalizedPatternPeriod] = []
    for item in periods:
        if item.weight is None:
            raise ValidationError("weighted_period requires weight for every period")
        if item.percentage is not None or item.amount is not None:
            raise ValidationError("weighted_period accepts weight only")
        normalized.append(
            NormalizedPatternPeriod(
                period_seq=item.period_seq,
                period_start_date=item.period_start_date,
                period_end_date=item.period_end_date,
                recognition_date=item.recognition_date,
                weight=quantize_persisted_amount(item.weight),
                percentage=None,
                amount=None,
            )
        )
    return normalized


def _normalize_explicit_percentages(periods: list[PrepaidPatternPeriodInput]) -> list[NormalizedPatternPeriod]:
    normalized: list[NormalizedPatternPeriod] = []
    total = Decimal("0")
    for item in periods:
        if item.percentage is None:
            raise ValidationError("explicit_percentages requires percentage for every period")
        if item.weight is not None or item.amount is not None:
            raise ValidationError("explicit_percentages accepts percentage only")
        pct = quantize_persisted_amount(item.percentage)
        total += pct
        normalized.append(
            NormalizedPatternPeriod(
                period_seq=item.period_seq,
                period_start_date=item.period_start_date,
                period_end_date=item.period_end_date,
                recognition_date=item.recognition_date,
                weight=None,
                percentage=pct,
                amount=None,
            )
        )
    if quantize_persisted_amount(total) != Decimal("1.000000"):
        raise ValidationError("explicit_percentages must sum exactly to 1.000000")
    return normalized


def _normalize_explicit_amounts(periods: list[PrepaidPatternPeriodInput], *, base_amount: Decimal) -> list[NormalizedPatternPeriod]:
    normalized: list[NormalizedPatternPeriod] = []
    total = Decimal("0")
    for item in periods:
        if item.amount is None:
            raise ValidationError("explicit_amounts requires amount for every period")
        if item.weight is not None or item.percentage is not None:
            raise ValidationError("explicit_amounts accepts amount only")
        amount = quantize_persisted_amount(item.amount)
        total += amount
        normalized.append(
            NormalizedPatternPeriod(
                period_seq=item.period_seq,
                period_start_date=item.period_start_date,
                period_end_date=item.period_end_date,
                recognition_date=item.recognition_date,
                weight=None,
                percentage=None,
                amount=amount,
            )
        )
    if quantize_persisted_amount(total) != quantize_persisted_amount(base_amount):
        raise ValidationError("explicit_amounts must sum exactly to base_amount_contract_currency")
    return normalized


def _period_to_json(period: NormalizedPatternPeriod) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "period_seq": period.period_seq,
        "period_start_date": period.period_start_date.isoformat(),
        "period_end_date": period.period_end_date.isoformat(),
        "recognition_date": period.recognition_date.isoformat(),
    }
    if period.weight is not None:
        payload["weight"] = _decimal_text(period.weight)
    if period.percentage is not None:
        payload["percentage"] = _decimal_text(period.percentage)
    if period.amount is not None:
        payload["amount"] = _decimal_text(period.amount)
    return payload


def normalize_pattern(prepaid: PrepaidInput) -> NormalizedPattern:
    if prepaid.period_frequency.lower() != "monthly":
        raise ValidationError("period_frequency must be monthly in 1D.4 core")

    base_amount = quantize_persisted_amount(prepaid.base_amount_contract_currency)

    if prepaid.pattern_type == PrepaidPatternType.straight_line:
        if prepaid.periods:
            raise ValidationError("straight_line pattern forbids periods")
        normalized_periods = _normalize_straight_line_periods(
            term_start=prepaid.term_start_date,
            term_end=prepaid.term_end_date,
        )
    else:
        source_periods = prepaid.periods or []
        if not source_periods:
            raise ValidationError("periods are required for non-straight_line patterns")
        ordered = _validate_period_order(
            source_periods,
            term_start=prepaid.term_start_date,
            term_end=prepaid.term_end_date,
        )
        if prepaid.pattern_type == PrepaidPatternType.weighted_period:
            normalized_periods = _normalize_weighted_periods(ordered)
        elif prepaid.pattern_type == PrepaidPatternType.explicit_percentages:
            normalized_periods = _normalize_explicit_percentages(ordered)
        elif prepaid.pattern_type == PrepaidPatternType.explicit_amounts:
            normalized_periods = _normalize_explicit_amounts(ordered, base_amount=base_amount)
        else:
            raise ValidationError(f"Unsupported pattern type {prepaid.pattern_type}")

    canonical_json = {
        "pattern_type": prepaid.pattern_type.value,
        "period_frequency": "monthly",
        "periods": [_period_to_json(item) for item in sorted(normalized_periods, key=lambda row: row.period_seq)],
    }
    return NormalizedPattern(
        pattern_type=prepaid.pattern_type,
        period_frequency="monthly",
        periods=sorted(normalized_periods, key=lambda row: row.period_seq),
        canonical_json=canonical_json,
    )

