from __future__ import annotations

from financeops.modules.payment.domain.enums import PaymentProvider
from financeops.modules.payment.infrastructure.providers.base import AbstractPaymentProvider
from financeops.modules.payment.infrastructure.providers.razorpay import RazorpayPaymentProvider
from financeops.modules.payment.infrastructure.providers.stripe import StripePaymentProvider


_PROVIDER_REGISTRY: dict[PaymentProvider, type[AbstractPaymentProvider]] = {
    PaymentProvider.STRIPE: StripePaymentProvider,
    PaymentProvider.RAZORPAY: RazorpayPaymentProvider,
}


def get_provider(provider: PaymentProvider) -> AbstractPaymentProvider:
    cls = _PROVIDER_REGISTRY[provider]
    return cls()


def list_providers() -> tuple[PaymentProvider, ...]:
    return tuple(_PROVIDER_REGISTRY.keys())
