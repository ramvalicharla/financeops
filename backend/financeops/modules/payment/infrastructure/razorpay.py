from __future__ import annotations

from financeops.modules.payment.infrastructure.providers.razorpay import (
    RazorpayPaymentProvider,
)


class RazorpayClient(RazorpayPaymentProvider):
    """Backward-compatible alias for startup dependency checks."""


__all__ = ["RazorpayClient"]
