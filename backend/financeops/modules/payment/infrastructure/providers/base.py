from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal

from financeops.modules.payment.domain.enums import BillingCycle
from financeops.modules.payment.domain.schemas import PaymentProviderResult


class AbstractPaymentProvider(ABC):
    @abstractmethod
    async def create_customer(
        self,
        tenant_id: str,
        email: str,
        name: str,
        metadata: dict,
    ) -> PaymentProviderResult: ...

    @abstractmethod
    async def create_subscription(
        self,
        customer_id: str,
        plan_id: str,
        billing_cycle: BillingCycle,
        trial_days: int,
        metadata: dict,
    ) -> PaymentProviderResult: ...

    @abstractmethod
    async def upgrade_subscription(
        self,
        subscription_id: str,
        new_plan_id: str,
        prorate: bool,
    ) -> PaymentProviderResult: ...

    @abstractmethod
    async def cancel_subscription(
        self,
        subscription_id: str,
        cancel_at_period_end: bool,
    ) -> PaymentProviderResult: ...

    @abstractmethod
    async def reactivate_subscription(self, subscription_id: str) -> PaymentProviderResult: ...

    @abstractmethod
    async def create_invoice(
        self,
        customer_id: str,
        line_items: list[dict],
        metadata: dict,
    ) -> PaymentProviderResult: ...

    @abstractmethod
    async def pay_invoice(
        self,
        invoice_id: str,
        payment_method_id: str,
    ) -> PaymentProviderResult: ...

    @abstractmethod
    async def create_payment_method(
        self,
        customer_id: str,
        payment_method_token: str,
    ) -> PaymentProviderResult: ...

    @abstractmethod
    async def set_default_payment_method(
        self,
        customer_id: str,
        payment_method_id: str,
    ) -> PaymentProviderResult: ...

    @abstractmethod
    async def detach_payment_method(
        self,
        payment_method_id: str,
    ) -> PaymentProviderResult: ...

    @abstractmethod
    async def create_top_up_charge(
        self,
        customer_id: str,
        amount: Decimal,
        currency: str,
        credits: int,
        metadata: dict,
    ) -> PaymentProviderResult: ...

    @abstractmethod
    async def verify_webhook(
        self,
        payload: bytes,
        signature: str,
        secret: str,
    ) -> bool: ...

    @abstractmethod
    async def parse_webhook_event(self, payload: dict) -> tuple[str, dict]: ...

    @abstractmethod
    async def get_billing_portal_url(
        self,
        customer_id: str,
        return_url: str,
    ) -> str: ...
