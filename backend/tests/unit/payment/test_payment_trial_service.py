from __future__ import annotations

from datetime import date

from financeops.modules.payment.application.trial_service import TrialService


def test_trial_window_for_positive_days() -> None:
    start, end = TrialService.resolve_trial_window(trial_days=14, start_date=date(2026, 1, 1))
    assert start == date(2026, 1, 1)
    assert end == date(2026, 1, 15)


def test_trial_window_for_zero_days() -> None:
    start, end = TrialService.resolve_trial_window(trial_days=0)
    assert start is None
    assert end is None


def test_trial_conversion_decisions() -> None:
    assert TrialService.should_convert_to_active(
        trial_end=date(2026, 1, 5),
        has_payment_method=True,
        as_of=date(2026, 1, 5),
    )
    assert TrialService.should_mark_incomplete(
        trial_end=date(2026, 1, 5),
        has_payment_method=False,
        as_of=date(2026, 1, 6),
    )

