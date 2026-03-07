from __future__ import annotations

from decimal import Decimal

from financeops.services.fx.conversion import apply_rate_to_lines, convert_amount


def test_convert_amount_uses_financial_precision() -> None:
    converted = convert_amount(Decimal("100.00"), Decimal("83.123456"))
    assert converted == Decimal("8312.35")


def test_apply_rate_to_lines_returns_linewise_output() -> None:
    lines = apply_rate_to_lines(
        line_items=[("txn-1", Decimal("10.00")), ("txn-2", Decimal("20.00"))],
        rate=Decimal("2.500000"),
    )
    assert len(lines) == 2
    assert lines[0].converted_amount == Decimal("25.00")
    assert lines[1].converted_amount == Decimal("50.00")
