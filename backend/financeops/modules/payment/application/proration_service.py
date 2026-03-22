from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP


@dataclass(frozen=True)
class ProrationComputation:
    credit_amount: Decimal
    debit_amount: Decimal
    net_adjustment: Decimal
    currency: str


class ProrationService:
    @staticmethod
    def calculate(
        *,
        from_plan_price: Decimal,
        to_plan_price: Decimal,
        days_remaining: int,
        total_days: int,
        currency: str,
    ) -> ProrationComputation:
        if total_days <= 0:
            raise ValueError("total_days must be positive")
        prorate_factor = Decimal(days_remaining) / Decimal(total_days)
        unused_credit = (from_plan_price * prorate_factor).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        remaining_debit = (to_plan_price * prorate_factor).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        net = (remaining_debit - unused_credit).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return ProrationComputation(
            credit_amount=unused_credit,
            debit_amount=remaining_debit,
            net_adjustment=net,
            currency=currency.upper(),
        )
