from __future__ import annotations

from financeops.modules.payment.domain.enums import PaymentProvider
from financeops.modules.payment.infrastructure.providers.registry import get_provider


class WebhookVerifier:
    async def verify(
        self,
        *,
        provider: PaymentProvider,
        payload: bytes,
        signature: str,
        secret: str,
    ) -> bool:
        provider_impl = get_provider(provider)
        return await provider_impl.verify_webhook(payload=payload, signature=signature, secret=secret)
