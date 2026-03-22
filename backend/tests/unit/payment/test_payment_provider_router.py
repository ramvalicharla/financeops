from __future__ import annotations

from financeops.modules.payment.application.provider_router import resolve_provider
from financeops.modules.payment.domain.enums import PaymentProvider
from financeops.modules.payment.infrastructure.providers.registry import list_providers


def test_resolve_provider_by_country() -> None:
    assert resolve_provider("IN") == PaymentProvider.RAZORPAY
    assert resolve_provider("US") == PaymentProvider.STRIPE


def test_resolve_provider_with_override() -> None:
    assert resolve_provider("IN", override=PaymentProvider.STRIPE) == PaymentProvider.STRIPE


def test_provider_registry_lists_both_providers() -> None:
    providers = set(list_providers())
    assert providers == {PaymentProvider.STRIPE, PaymentProvider.RAZORPAY}
