from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.config import settings
from financeops.core.exceptions import NotFoundError, ValidationError
from financeops.db.models.payment import BillingInvoice, BillingPayment, BillingPlan, TenantSubscription
from financeops.modules.payment.application.entitlement_service import EntitlementService
from financeops.modules.payment.application.invoice_service import InvoiceService
from financeops.modules.payment.application.webhook_service import WebhookService
from financeops.modules.payment.domain.enums import PaymentProvider
from financeops.modules.payment.infrastructure.providers.registry import get_provider
from financeops.services.audit_writer import AuditEvent, AuditWriter


class SaaSBillingService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._invoice_service = InvoiceService(session)
        self._entitlement_service = EntitlementService(session)

    async def _get_latest_subscription(self, tenant_id: uuid.UUID) -> TenantSubscription:
        row = (
            await self._session.execute(
                select(TenantSubscription)
                .where(TenantSubscription.tenant_id == tenant_id)
                .order_by(TenantSubscription.created_at.desc(), TenantSubscription.id.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if row is None:
            raise NotFoundError("Subscription not found")
        return row

    async def _get_plan(self, *, tenant_id: uuid.UUID, plan_id: uuid.UUID) -> BillingPlan:
        row = (
            await self._session.execute(
                select(BillingPlan).where(BillingPlan.tenant_id == tenant_id, BillingPlan.id == plan_id)
            )
        ).scalar_one_or_none()
        if row is None:
            raise NotFoundError("Billing plan not found")
        return row

    async def create_checkout_session(
        self,
        *,
        tenant_id: uuid.UUID,
        return_url: str,
    ) -> dict[str, str]:
        subscription = await self._get_latest_subscription(tenant_id)
        provider = get_provider(PaymentProvider(subscription.provider))
        url = await provider.get_billing_portal_url(
            customer_id=subscription.provider_customer_id,
            return_url=return_url,
        )
        return {
            "provider": subscription.provider,
            "url": url,
            "subscription_id": str(subscription.id),
        }

    async def generate_invoice(
        self,
        *,
        tenant_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        subscription_id: uuid.UUID | None = None,
        due_in_days: int = 7,
    ) -> BillingInvoice:
        if due_in_days < 0:
            raise ValidationError("due_in_days must be >= 0")

        subscription = await self._get_latest_subscription(tenant_id)
        if subscription_id and subscription.id != subscription_id:
            subscription = await self._invoice_service.ensure_subscription(
                tenant_id=tenant_id,
                subscription_id=subscription_id,
            )

        plan = await self._get_plan(tenant_id=tenant_id, plan_id=subscription.plan_id)

        currency = (plan.currency or subscription.billing_currency or "USD").upper()
        base_amount = plan.price
        if base_amount is None:
            if currency == "INR":
                base_amount = Decimal(str(plan.base_price_inr))
            else:
                base_amount = Decimal(str(plan.base_price_usd))

        period_start = subscription.current_period_start
        period_end = subscription.current_period_end + timedelta(days=1)

        line_items: list[dict[str, Any]] = [
            {
                "description": f"{plan.name or plan.plan_tier} subscription",
                "amount": str(base_amount),
                "currency": currency,
                "type": "base_fee",
            }
        ]

        entitlements = await self._entitlement_service.list_latest_tenant_entitlements(tenant_id=tenant_id)
        if not entitlements:
            await self._entitlement_service.refresh_tenant_entitlements(
                tenant_id=tenant_id,
                actor_user_id=actor_user_id,
            )
            entitlements = await self._entitlement_service.list_latest_tenant_entitlements(tenant_id=tenant_id)

        usage_total = Decimal("0")
        for entitlement in entitlements:
            if entitlement.access_type not in {"limit", "quota"}:
                continue
            if entitlement.effective_limit is None:
                continue
            price_per_unit = Decimal(
                str((entitlement.metadata_json or {}).get("price_per_unit", "0"))
            )
            if price_per_unit <= Decimal("0"):
                continue
            overage_charge = await self._entitlement_service.calculate_overage_charge(
                tenant_id=tenant_id,
                feature_name=entitlement.feature_name,
                unit_price=price_per_unit,
                period_start=period_start,
                period_end=period_end,
                included_limit=entitlement.effective_limit,
            )
            if overage_charge <= Decimal("0"):
                continue
            usage_total += overage_charge
            line_items.append(
                {
                    "description": f"Overage: {entitlement.feature_name}",
                    "amount": str(overage_charge),
                    "currency": currency,
                    "type": "usage_overage",
                }
            )

        subtotal = base_amount + usage_total
        tax = Decimal("0")
        total = subtotal + tax

        provider = get_provider(PaymentProvider(subscription.provider))
        provider_result = await provider.create_invoice(
            customer_id=subscription.provider_customer_id,
            line_items=line_items,
            metadata={
                "tenant_id": str(tenant_id),
                "subscription_id": str(subscription.id),
            },
        )
        provider_invoice_id = provider_result.provider_id or f"local_{uuid.uuid4().hex}"

        due_date = datetime.now(UTC).date() + timedelta(days=due_in_days)
        invoice = await self._invoice_service.create_invoice_record(
            tenant_id=tenant_id,
            subscription_id=subscription.id,
            provider_invoice_id=provider_invoice_id,
            currency=currency,
            subtotal=subtotal,
            tax=tax,
            total=total,
            due_date=due_date,
            line_items=line_items,
        )

        # Append a payment intent placeholder for auditability.
        await AuditWriter.insert_financial_record(
            self._session,
            model_class=BillingPayment,
            tenant_id=tenant_id,
            record_data={
                "invoice_id": str(invoice.id),
                "payment_status": "pending",
                "provider_reference": provider_invoice_id,
                "amount": str(total),
            },
            values={
                "invoice_id": invoice.id,
                "amount": total,
                "payment_status": "pending",
                "provider_reference": provider_invoice_id,
                "provider": subscription.provider,
                "metadata_json": {
                    "provider_raw_success": provider_result.success,
                    "provider_error": provider_result.error_message,
                },
            },
            audit=AuditEvent(
                tenant_id=tenant_id,
                user_id=actor_user_id,
                action="billing.invoice.generated",
                resource_type="billing_invoice",
                resource_id=str(invoice.id),
                new_value={"total": str(total), "currency": currency},
            ),
        )

        return invoice

    async def process_webhook(
        self,
        *,
        provider: PaymentProvider,
        payload: bytes,
        signature: str,
        tenant_id: uuid.UUID,
    ) -> None:
        secret = (
            settings.STRIPE_SECRET_KEY
            if provider == PaymentProvider.STRIPE
            else settings.RAZORPAY_KEY_SECRET
        )
        service = WebhookService(self._session)
        await service.handle_webhook(
            provider=provider,
            payload=payload,
            signature=signature,
            secret=secret,
            tenant_id=tenant_id,
        )
