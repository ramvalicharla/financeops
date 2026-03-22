from __future__ import annotations

from datetime import UTC, date, datetime


class TrialService:
    @staticmethod
    def resolve_trial_window(*, trial_days: int, start_date: date | None = None) -> tuple[date | None, date | None]:
        if trial_days <= 0:
            return None, None
        start = start_date or datetime.now(UTC).date()
        return start, date.fromordinal(start.toordinal() + trial_days)

    @staticmethod
    def should_convert_to_active(*, trial_end: date | None, has_payment_method: bool, as_of: date | None = None) -> bool:
        if trial_end is None:
            return False
        now_date = as_of or datetime.now(UTC).date()
        return now_date >= trial_end and has_payment_method

    @staticmethod
    def should_mark_incomplete(*, trial_end: date | None, has_payment_method: bool, as_of: date | None = None) -> bool:
        if trial_end is None:
            return False
        now_date = as_of or datetime.now(UTC).date()
        return now_date >= trial_end and not has_payment_method
