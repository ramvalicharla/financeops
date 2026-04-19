from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.payment import BillingInvoice, BillingPayment, TenantSubscription, WebhookEvent
from financeops.modules.payment.domain.enums import PaymentProvider
from financeops.modules.payment.infrastructure.providers.registry import get_provider
from financeops.services.audit_writer import AuditEvent, AuditWriter

log = logging.getLogger(__name__)


class WebhookService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _claim_webhook_event(
        self,
        *,
        tenant_id: uuid.UUID,
        provider: PaymentProvider,
        provider_event_id: str,
        canonical_event_type: str,
        parsed_payload: dict[str, Any],
    ) -> bool:
        try:
            async with self._session.begin_nested():
                await AuditWriter.insert_financial_record(
                    self._session,
                    model_class=WebhookEvent,
                    tenant_id=tenant_id,
                    record_data={
                        "provider": provider.value,
                        "provider_event_id": provider_event_id,
                        "event_type": canonical_event_type,
                        "processed": "false",
                    },
                    values={
                        "provider": provider.value,
                        "provider_event_id": provider_event_id,
                        "event_type": canonical_event_type,
                        "payload": parsed_payload,
                        "processed": False,
                        "processed_at": None,
                        "processing_error": None,
                    },
                )
        except IntegrityError:
            return False
        return True

    async def handle_webhook(
        self,
        *,
        provider: PaymentProvider,
        payload: bytes,
        signature: str,
        secret: str,
        tenant_id: uuid.UUID,
    ) -> None:
        provider_impl = get_provider(provider)
        verified = await provider_impl.verify_webhook(payload=payload, signature=signature, secret=secret)
        if not verified:
            log.warning(
                "payment_webhook_verification_failed provider=%s tenant_id=%s",
                provider.value,
                tenant_id,
            )
            return

        parsed_payload = json.loads(payload.decode("utf-8")) if payload else {}
        canonical_event_type, normalized_data = await provider_impl.parse_webhook_event(parsed_payload)
        provider_event_id = str(
            normalized_data.get("provider_event_id") or parsed_payload.get("id") or ""
        ).strip()
        if not provider_event_id:
            # Deterministic fallback keeps webhook processing idempotent even when
            # provider payloads omit an explicit event identifier.
            payload_hash = hashlib.sha256(payload or b"").hexdigest()
            provider_event_id = (
                f"derived:{provider.value}:{canonical_event_type}:{payload_hash}"
            )
        normalized_data["provider_event_id"] = provider_event_id

        claimed = await self._claim_webhook_event(
            tenant_id=tenant_id,
            provider=provider,
            provider_event_id=provider_event_id,
            canonical_event_type=canonical_event_type,
            parsed_payload=parsed_payload,
        )
        if not claimed:
            log.info(
                "payment_webhook_duplicate_ignored provider=%s tenant_id=%s event_id=%s",
                provider.value,
                tenant_id,
                provider_event_id,
            )
            return
        log.info(
            "payment_webhook_claimed provider=%s tenant_id=%s event_id=%s event_type=%s",
            provider.value,
            tenant_id,
            provider_event_id,
            canonical_event_type,
        )

        try:
            await self._route_event(
                tenant_id=tenant_id,
                canonical_event_type=canonical_event_type,
                normalized_data=normalized_data,
                provider_event_id=provider_event_id,
            )
        except Exception as exc:  # pragma: no cover - defensive path for webhook resilience
            log.warning(
                "payment_webhook_processing_failed provider=%s tenant_id=%s event_id=%s event_type=%s error=%s",
                provider.value,
                tenant_id,
                provider_event_id,
                canonical_event_type,
                exc,
            )
            return
        log.info(
            "payment_webhook_processed provider=%s tenant_id=%s event_id=%s event_type=%s",
            provider.value,
            tenant_id,
            provider_event_id,
            canonical_event_type,
        )

    async def _route_event(
        self,
        *,
        tenant_id: uuid.UUID,
        canonical_event_type: str,
        normalized_data: dict[str, Any],
        provider_event_id: str,
    ) -> None:
        if canonical_event_type in {
            "invoice.paid",
            "invoice.payment_failed",
            "payment.succeeded",
            "payment.failed",
        }:
            await self._apply_invoice_event(
                tenant_id=tenant_id,
                canonical_event_type=canonical_event_type,
                normalized_data=normalized_data,
                provider_event_id=provider_event_id,
            )
            return
        if canonical_event_type.startswith("subscription."):
            await self._apply_subscription_event(
                tenant_id=tenant_id,
                canonical_event_type=canonical_event_type,
                normalized_data=normalized_data,
            )

    @staticmethod
    def _extract_invoice_id(normalized_data: dict[str, Any]) -> str | None:
        obj = normalized_data.get("object")
        if not isinstance(obj, dict):
            return None
        # Stripe
        if obj.get("id"):
            return str(obj["id"])
        # Razorpay
        invoice_payload = obj.get("invoice", {}).get("entity") if isinstance(obj.get("invoice"), dict) else None
        if isinstance(invoice_payload, dict) and invoice_payload.get("id"):
            return str(invoice_payload["id"])
        payment_invoice_id = obj.get("payment", {}).get("entity", {}).get("invoice_id")
        if payment_invoice_id:
            return str(payment_invoice_id)
        return None

    @staticmethod
    def _extract_subscription_id(normalized_data: dict[str, Any]) -> str | None:
        obj = normalized_data.get("object")
        if not isinstance(obj, dict):
            return None
        # Stripe
        if obj.get("id") and str(obj.get("object", "")).startswith("subscription"):
            return str(obj["id"])
        if obj.get("subscription"):
            return str(obj["subscription"])
        # Razorpay
        subscription_payload = obj.get("subscription", {}).get("entity") if isinstance(obj.get("subscription"), dict) else None
        if isinstance(subscription_payload, dict) and subscription_payload.get("id"):
            return str(subscription_payload["id"])
        payment_subscription_id = obj.get("payment", {}).get("entity", {}).get("subscription_id")
        if payment_subscription_id:
            return str(payment_subscription_id)
        return None

    @staticmethod
    def _extract_amount(normalized_data: dict[str, Any], default_total: Decimal) -> Decimal:
        obj = normalized_data.get("object")
        if not isinstance(obj, dict):
            return default_total
        # Stripe stores smallest unit integers.
        stripe_amount = obj.get("amount_paid") or obj.get("amount_due")
        if isinstance(stripe_amount, int):
            return Decimal(str(stripe_amount)) / Decimal("100")
        # Razorpay smallest unit integer.
        razorpay_amount = (
            obj.get("payment", {}).get("entity", {}).get("amount")
            if isinstance(obj.get("payment"), dict)
            else None
        )
        if isinstance(razorpay_amount, int):
            return Decimal(str(razorpay_amount)) / Decimal("100")
        return default_total

    async def _append_subscription_status(
        self,
        *,
        source: TenantSubscription,
        status: str,
        metadata: dict[str, Any],
    ) -> TenantSubscription:
        if source.status == status:
            return source
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=TenantSubscription,
            tenant_id=source.tenant_id,
            record_data={
                "plan_id": str(source.plan_id),
                "provider": source.provider,
                "provider_subscription_id": source.provider_subscription_id,
                "status": status,
            },
            values={
                "plan_id": source.plan_id,
                "provider": source.provider,
                "provider_subscription_id": source.provider_subscription_id,
                "provider_customer_id": source.provider_customer_id,
                "status": status,
                "billing_cycle": source.billing_cycle,
                "current_period_start": source.current_period_start,
                "current_period_end": source.current_period_end,
                "trial_start": source.trial_start,
                "trial_end": source.trial_end,
                "start_date": source.start_date or source.current_period_start,
                "end_date": source.end_date or source.current_period_end,
                "trial_end_date": source.trial_end_date or source.trial_end,
                "auto_renew": source.auto_renew,
                "cancelled_at": source.cancelled_at,
                "cancel_at_period_end": source.cancel_at_period_end,
                "onboarding_mode": source.onboarding_mode,
                "billing_country": source.billing_country,
                "billing_currency": source.billing_currency,
                "metadata_json": metadata,
            },
            audit=AuditEvent(
                tenant_id=source.tenant_id,
                user_id=None,
                action="billing.subscription.webhook_status_updated",
                resource_type="tenant_subscription",
                resource_id=str(source.id),
                new_value={"status": status},
            ),
        )

    async def _apply_subscription_event(
        self,
        *,
        tenant_id: uuid.UUID,
        canonical_event_type: str,
        normalized_data: dict[str, Any],
    ) -> None:
        provider_subscription_id = self._extract_subscription_id(normalized_data)
        if not provider_subscription_id:
            return
        subscription = (
            await self._session.execute(
                select(TenantSubscription)
                .where(
                    TenantSubscription.tenant_id == tenant_id,
                    TenantSubscription.provider_subscription_id == provider_subscription_id,
                )
                .order_by(TenantSubscription.created_at.desc(), TenantSubscription.id.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if subscription is None:
            return

        status_map = {
            "subscription.created": "active",
            "subscription.updated": "active",
            "subscription.cancelled": "cancelled",
        }
        next_status = status_map.get(canonical_event_type)
        if not next_status:
            return
        metadata = dict(subscription.metadata_json or {})
        metadata.update(
            {
                "webhook_last_event_type": canonical_event_type,
                "webhook_last_event_at": datetime.now(UTC).isoformat(),
            }
        )
        await self._append_subscription_status(
            source=subscription,
            status=next_status,
            metadata=metadata,
        )

    async def _apply_invoice_event(
        self,
        *,
        tenant_id: uuid.UUID,
        canonical_event_type: str,
        normalized_data: dict[str, Any],
        provider_event_id: str,
    ) -> None:
        provider_invoice_id = self._extract_invoice_id(normalized_data)
        if not provider_invoice_id:
            return
        invoice = (
            await self._session.execute(
                select(BillingInvoice)
                .where(
                    BillingInvoice.tenant_id == tenant_id,
                    BillingInvoice.provider_invoice_id == provider_invoice_id,
                )
                .order_by(BillingInvoice.created_at.desc(), BillingInvoice.id.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if invoice is None:
            return

        now = datetime.now(UTC)
        is_success = canonical_event_type in {"invoice.paid", "payment.succeeded"}
        next_status = "paid" if is_success else "uncollectible"

        revised_invoice = await AuditWriter.insert_financial_record(
            self._session,
            model_class=BillingInvoice,
            tenant_id=tenant_id,
            record_data={
                "subscription_id": str(invoice.subscription_id),
                "provider_invoice_id": invoice.provider_invoice_id,
                "status": next_status,
            },
            values={
                "subscription_id": invoice.subscription_id,
                "provider_invoice_id": invoice.provider_invoice_id,
                "status": next_status,
                "currency": invoice.currency,
                "subtotal": invoice.subtotal,
                "tax": invoice.tax,
                "total": invoice.total,
                "amount": invoice.amount or invoice.total,
                "issued_at": invoice.issued_at or invoice.created_at,
                "due_at": invoice.due_at,
                "credits_applied": invoice.credits_applied,
                "due_date": invoice.due_date,
                "paid_at": now if is_success else invoice.paid_at,
                "voided_at": invoice.voided_at,
                "invoice_pdf_url": invoice.invoice_pdf_url,
                "line_items": list(invoice.line_items or []),
            },
            audit=AuditEvent(
                tenant_id=tenant_id,
                user_id=None,
                action="billing.invoice.webhook_status_updated",
                resource_type="billing_invoice",
                resource_id=str(invoice.id),
                new_value={"status": next_status},
            ),
        )

        amount = self._extract_amount(normalized_data, default_total=invoice.total)
        await AuditWriter.insert_financial_record(
            self._session,
            model_class=BillingPayment,
            tenant_id=tenant_id,
            record_data={
                "invoice_id": str(revised_invoice.id),
                "payment_status": "succeeded" if is_success else "failed",
                "provider_reference": provider_event_id,
                "amount": str(amount),
            },
            values={
                "invoice_id": revised_invoice.id,
                "amount": amount,
                "payment_status": "succeeded" if is_success else "failed",
                "provider_reference": provider_event_id,
                "provider": None,
                "metadata_json": {
                    "canonical_event_type": canonical_event_type,
                    "provider_invoice_id": provider_invoice_id,
                },
            },
            audit=AuditEvent(
                tenant_id=tenant_id,
                user_id=None,
                action="billing.payment.webhook_recorded",
                resource_type="billing_payment",
                new_value={
                    "status": "succeeded" if is_success else "failed",
                    "provider_reference": provider_event_id,
                },
            ),
        )

        subscription = (
            await self._session.execute(
                select(TenantSubscription)
                .where(
                    TenantSubscription.tenant_id == tenant_id,
                    TenantSubscription.id == invoice.subscription_id,
                )
                .order_by(TenantSubscription.created_at.desc(), TenantSubscription.id.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if subscription is None:
            return
        metadata = dict(subscription.metadata_json or {})
        metadata.update(
            {
                "webhook_last_invoice_event": canonical_event_type,
                "webhook_last_invoice_event_at": now.isoformat(),
            }
        )
        await self._append_subscription_status(
            source=subscription,
            status="active" if is_success else "past_due",
            metadata=metadata,
        )
