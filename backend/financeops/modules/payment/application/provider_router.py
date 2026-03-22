from __future__ import annotations

from financeops.modules.payment.domain.enums import PaymentProvider

INDIA_PROVIDER = PaymentProvider.RAZORPAY
GLOBAL_PROVIDER = PaymentProvider.STRIPE


def resolve_provider(
    billing_country: str,
    override: PaymentProvider | None = None,
) -> PaymentProvider:
    if override is not None:
        return override
    if billing_country.upper() == "IN":
        return INDIA_PROVIDER
    return GLOBAL_PROVIDER
