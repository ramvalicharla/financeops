from __future__ import annotations

from decimal import Decimal

from financeops.services.accounting_common.quantization_policy import (
    quantize_persisted_amount,
    quantize_rate,
)
from financeops.services.lease.pv_calculator import periods_per_year


def compute_period_interest(
    *,
    opening_liability_reporting_currency: Decimal,
    annual_discount_rate: Decimal,
    payment_frequency: str,
) -> Decimal:
    period_rate = quantize_rate(annual_discount_rate / Decimal(str(periods_per_year(payment_frequency))))
    return quantize_persisted_amount(opening_liability_reporting_currency * period_rate)

