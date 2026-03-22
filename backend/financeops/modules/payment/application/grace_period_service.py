from __future__ import annotations

from datetime import UTC, datetime, timedelta


class GracePeriodService:
    DEFAULT_GRACE_DAYS = 7

    @classmethod
    def resolve_grace_days(cls, *, plan_grace_days: int | None = None) -> int:
        if plan_grace_days is None or plan_grace_days <= 0:
            return cls.DEFAULT_GRACE_DAYS
        return plan_grace_days

    @classmethod
    def grace_window(
        cls,
        *,
        started_at: datetime | None = None,
        grace_days: int | None = None,
    ) -> tuple[datetime, datetime, int]:
        days = cls.resolve_grace_days(plan_grace_days=grace_days)
        start = started_at or datetime.now(UTC)
        return start, start + timedelta(days=days), days

    @staticmethod
    def has_expired(*, grace_period_end: datetime, as_of: datetime | None = None) -> bool:
        now_ts = as_of or datetime.now(UTC)
        return now_ts >= grace_period_end
