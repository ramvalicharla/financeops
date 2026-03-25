from __future__ import annotations

from decimal import Decimal

from financeops.utils.display_scale import (
    DisplayScale,
    SCALE_DIVISORS,
    _format_indian_number,
    format_scaled_amount,
    get_effective_scale,
    scale_amount,
    scale_report_data,
)


def test_scale_amount_lakhs() -> None:
    assert scale_amount(Decimal("12345678.90"), DisplayScale.LAKHS) == Decimal("123.46")


def test_scale_amount_crores() -> None:
    assert scale_amount(Decimal("12345678.90"), DisplayScale.CRORES) == Decimal("1.23")


def test_scale_amount_millions() -> None:
    assert scale_amount(Decimal("12345678.90"), DisplayScale.MILLIONS) == Decimal("12.35")


def test_scale_amount_inr_unchanged() -> None:
    assert scale_amount(Decimal("12345.67"), DisplayScale.INR) == Decimal("12345.67")


def test_scale_amount_thousands() -> None:
    assert scale_amount(Decimal("12345678.90"), DisplayScale.THOUSANDS) == Decimal("12345.68")


def test_format_indian_number_correct() -> None:
    assert _format_indian_number(Decimal("12345678.90")) == "1,23,45,678.90"
    assert _format_indian_number(Decimal("1234567.89")) == "12,34,567.89"
    assert _format_indian_number(Decimal("123456.78")) == "1,23,456.78"
    assert _format_indian_number(Decimal("12345.67")) == "12,345.67"
    assert _format_indian_number(Decimal("1234.56")) == "1,234.56"


def test_format_scaled_lakhs() -> None:
    assert format_scaled_amount(Decimal("12345678"), DisplayScale.LAKHS) == "₹123.46L"


def test_format_scaled_crores() -> None:
    assert format_scaled_amount(Decimal("12345678"), DisplayScale.CRORES) == "₹1.23Cr"


def test_format_scaled_inr_indian_format() -> None:
    assert format_scaled_amount(Decimal("12345678"), DisplayScale.INR) == "₹1,23,45,678.00"


def test_negative_amount_lakhs() -> None:
    assert format_scaled_amount(Decimal("-5000000"), DisplayScale.LAKHS) == "₹-50.00L"


def test_zero_amount() -> None:
    assert format_scaled_amount(Decimal("0"), DisplayScale.LAKHS) == "₹0.00L"


def test_effective_scale_user_override_wins() -> None:
    assert get_effective_scale("CRORES", "LAKHS") == DisplayScale.CRORES


def test_effective_scale_tenant_default_used() -> None:
    assert get_effective_scale(None, "MILLIONS") == DisplayScale.MILLIONS


def test_effective_scale_platform_default_fallback() -> None:
    assert get_effective_scale(None, None) == DisplayScale.LAKHS


def test_scale_report_data_scales_amount_keys() -> None:
    report = {"revenue": Decimal("10000000"), "ebitda": Decimal("2000000"), "note": "ok"}
    scaled = scale_report_data(report, ["revenue", "ebitda"], DisplayScale.LAKHS)
    assert scaled["revenue"] == Decimal("100.00")
    assert scaled["ebitda"] == Decimal("20.00")


def test_scale_report_data_does_not_modify_original() -> None:
    report = {"revenue": Decimal("10000000")}
    _ = scale_report_data(report, ["revenue"], DisplayScale.LAKHS)
    assert report["revenue"] == Decimal("10000000")


def test_scale_report_data_adds_metadata_keys() -> None:
    scaled = scale_report_data({"revenue": Decimal("10000000")}, ["revenue"], DisplayScale.LAKHS)
    assert scaled["_display_scale"] == "LAKHS"
    assert scaled["_scale_label"] == "₹ in Lakhs"


def test_invalid_scale_falls_back_to_lakhs() -> None:
    assert get_effective_scale("INVALID", "INVALID") == DisplayScale.LAKHS


def test_all_scale_values_are_decimal_not_float() -> None:
    assert all(isinstance(value, Decimal) for value in SCALE_DIVISORS.values())

