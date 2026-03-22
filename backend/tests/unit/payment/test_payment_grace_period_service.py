from __future__ import annotations

from datetime import UTC, datetime, timedelta

from financeops.modules.payment.application.grace_period_service import GracePeriodService


def test_grace_window_defaults_to_seven_days() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    grace_start, grace_end, grace_days = GracePeriodService.grace_window(started_at=start)
    assert grace_start == start
    assert grace_end == start + timedelta(days=7)
    assert grace_days == 7


def test_grace_expiry_check() -> None:
    now = datetime(2026, 1, 10, tzinfo=UTC)
    assert GracePeriodService.has_expired(
        grace_period_end=now - timedelta(seconds=1),
        as_of=now,
    )
    assert not GracePeriodService.has_expired(
        grace_period_end=now + timedelta(seconds=1),
        as_of=now,
    )

