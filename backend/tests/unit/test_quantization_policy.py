from __future__ import annotations

from decimal import Decimal

from financeops.services.accounting_common.quantization_policy import (
    quantize_output_amount,
    quantize_persisted_amount,
    quantize_rate,
)


def test_quantization_policy_is_deterministic_half_up() -> None:
    assert quantize_rate(Decimal("1.2345674")) == Decimal("1.234567")
    assert quantize_rate(Decimal("1.2345675")) == Decimal("1.234568")
    assert quantize_persisted_amount(Decimal("99.9999994")) == Decimal("99.999999")
    assert quantize_persisted_amount(Decimal("99.9999995")) == Decimal("100.000000")
    assert quantize_output_amount(Decimal("12.345")) == Decimal("12.35")
    assert quantize_output_amount(Decimal("12.344")) == Decimal("12.34")
