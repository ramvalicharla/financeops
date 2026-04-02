from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import NotFoundError
from financeops.db.models.payment import BillingInvoice, TenantSubscription
from financeops.modules.payment.domain.enums import InvoiceStatus
from financeops.modules.payment.domain.schemas import PaymentProviderResult
from financeops.services.audit_writer import AuditWriter


class InvoiceService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_invoice_record(
        self,
        *,
        tenant_id: uuid.UUID,
        subscription_id: uuid.UUID,
        provider_invoice_id: str,
        currency: str,
        subtotal: Decimal,
        tax: Decimal,
        total: Decimal,
        due_date: date,
        line_items: list[dict[str, Any]],
    ) -> BillingInvoice:
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=BillingInvoice,
            tenant_id=tenant_id,
            record_data={
                "subscription_id": str(subscription_id),
                "provider_invoice_id": provider_invoice_id,
                "total": str(total),
            },
            values={
                "subscription_id": subscription_id,
                "provider_invoice_id": provider_invoice_id,
                "status": InvoiceStatus.OPEN.value,
                "currency": currency.upper(),
                "subtotal": subtotal,
                "tax": tax,
                "total": total,
                "amount": total,
                "issued_at": datetime.now(UTC),
                "due_at": datetime.combine(due_date, datetime.min.time(), tzinfo=UTC),
                "credits_applied": 0,
                "due_date": due_date,
                "paid_at": None,
                "voided_at": None,
                "invoice_pdf_url": None,
                "line_items": line_items,
            },
        )

    async def mark_paid(
        self,
        *,
        tenant_id: uuid.UUID,
        invoice_id: uuid.UUID,
        payment_result: PaymentProviderResult,
    ) -> BillingInvoice:
        invoice = (
            await self._session.execute(
                select(BillingInvoice).where(BillingInvoice.tenant_id == tenant_id, BillingInvoice.id == invoice_id)
            )
        ).scalar_one_or_none()
        if invoice is None:
            raise NotFoundError("Invoice not found")
        if not payment_result.success:
            return invoice
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=BillingInvoice,
            tenant_id=tenant_id,
            record_data={
                "subscription_id": str(invoice.subscription_id),
                "provider_invoice_id": invoice.provider_invoice_id,
                "status": InvoiceStatus.PAID.value,
                "total": str(invoice.total),
            },
            values={
                "subscription_id": invoice.subscription_id,
                "provider_invoice_id": invoice.provider_invoice_id,
                "status": InvoiceStatus.PAID.value,
                "currency": invoice.currency,
                "subtotal": invoice.subtotal,
                "tax": invoice.tax,
                "total": invoice.total,
                "amount": invoice.amount,
                "issued_at": invoice.issued_at,
                "due_at": invoice.due_at,
                "credits_applied": invoice.credits_applied,
                "due_date": invoice.due_date,
                "paid_at": datetime.now(UTC),
                "voided_at": invoice.voided_at,
                "invoice_pdf_url": invoice.invoice_pdf_url,
                "line_items": invoice.line_items,
            },
        )

    async def list_tenant_invoices(self, *, tenant_id: uuid.UUID) -> list[BillingInvoice]:
        return list(
            (
                await self._session.execute(
                    select(BillingInvoice)
                    .where(BillingInvoice.tenant_id == tenant_id)
                    .order_by(BillingInvoice.created_at.desc(), BillingInvoice.id.desc())
                )
            ).scalars()
        )

    async def ensure_subscription(self, *, tenant_id: uuid.UUID, subscription_id: uuid.UUID) -> TenantSubscription:
        row = (
            await self._session.execute(
                select(TenantSubscription).where(
                    TenantSubscription.tenant_id == tenant_id,
                    TenantSubscription.id == subscription_id,
                )
            )
        ).scalar_one_or_none()
        if row is None:
            raise NotFoundError("Subscription not found")
        return row
