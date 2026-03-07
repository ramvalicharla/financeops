from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from financeops.core.exceptions import ValidationError
from financeops.services.accounting_common.quantization_policy import (
    quantize_persisted_amount,
    quantize_rate,
)
from financeops.services.lease.payment_schedule import RegisteredLeasePayment

_FREQUENCY_TO_PERIODS: dict[str, int] = {
    "monthly": 12,
    "quarterly": 4,
    "annual": 1,
    "custom": 12,
}


@dataclass(frozen=True)
class PresentValueResult:
    lease_id: UUID
    payment_count: int
    discount_rate_per_period: Decimal
    present_value_lease_currency: Decimal
    present_value_reporting_currency: Decimal


def periods_per_year(payment_frequency: str) -> int:
    periods = _FREQUENCY_TO_PERIODS.get(payment_frequency.lower())
    if periods is None:
        raise ValidationError("Unsupported lease payment frequency")
    return periods


def calculate_present_value(
    *,
    lease_id: UUID,
    payments: list[RegisteredLeasePayment],
    annual_discount_rate: Decimal,
    payment_frequency: str,
    conversion_rate: Decimal,
) -> PresentValueResult:
    if not payments:
        return PresentValueResult(
            lease_id=lease_id,
            payment_count=0,
            discount_rate_per_period=Decimal("0.000000"),
            present_value_lease_currency=Decimal("0.000000"),
            present_value_reporting_currency=Decimal("0.000000"),
        )

    periods = periods_per_year(payment_frequency)
    discount_rate = quantize_rate(annual_discount_rate)
    period_rate = quantize_rate(discount_rate / Decimal(str(periods)))

    present_value_lease_currency = Decimal("0")
    for idx, payment in enumerate(payments, start=1):
        denominator = (Decimal("1") + period_rate) ** idx
        if denominator == Decimal("0"):
            raise ValidationError("Invalid discount denominator in present value calculation")
        discounted = payment.payment_amount_lease_currency / denominator
        present_value_lease_currency += discounted

    pv_lease_quantized = quantize_persisted_amount(present_value_lease_currency)
    pv_reporting = quantize_persisted_amount(pv_lease_quantized * quantize_rate(conversion_rate))

    return PresentValueResult(
        lease_id=lease_id,
        payment_count=len(payments),
        discount_rate_per_period=period_rate,
        present_value_lease_currency=pv_lease_quantized,
        present_value_reporting_currency=pv_reporting,
    )
