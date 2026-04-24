from __future__ import annotations

from datetime import date
from decimal import Decimal


def test_mis_dashboard_returns_empty_when_no_snapshots() -> None:
    from financeops.modules.mis_manager.api.routes import (
        _aggregate_metrics,
        _build_empty_dashboard,
    )

    # With no normalized lines every metric must be zero.
    totals = _aggregate_metrics([])
    assert totals["revenue"] == Decimal("0")
    assert totals["gross_profit"] == Decimal("0")
    assert totals["ebitda"] == Decimal("0")
    assert totals["net_profit"] == Decimal("0")

    # The empty dashboard structure must match the frontend schema exactly.
    dashboard = _build_empty_dashboard("ent-123", "2024-03-01")
    assert dashboard["entity_id"] == "ent-123"
    assert dashboard["period"] == "2024-03-01"
    assert dashboard["revenue"] == "0"
    assert dashboard["gross_profit"] == "0"
    assert dashboard["ebitda"] == "0"
    assert dashboard["net_profit"] == "0"
    assert dashboard["revenue_change_pct"] == "0"
    assert dashboard["line_items"] == []
    assert dashboard["chart_data"] == []


def test_mis_periods_returns_available_periods() -> None:
    from financeops.modules.mis_manager.api.routes import _parse_period, _period_label

    # YYYY-MM format maps to first day of month.
    assert _parse_period("2024-03") == date(2024, 3, 1)
    assert _parse_period("2024-12") == date(2024, 12, 1)

    # YYYY-MM-DD passes through unchanged.
    assert _parse_period("2024-03-15") == date(2024, 3, 15)

    # Labels are human-readable month-year strings.
    assert _period_label(date(2024, 3, 1)) == "Mar 2024"
    assert _period_label(date(2024, 12, 1)) == "Dec 2024"
    assert _period_label(date(2025, 1, 1)) == "Jan 2025"
