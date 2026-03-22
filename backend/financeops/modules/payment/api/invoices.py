from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user
from financeops.db.models.payment import BillingInvoice
from financeops.db.models.users import IamUser
from financeops.modules.payment.application.invoice_service import InvoiceService
from financeops.modules.payment.infrastructure.providers.registry import get_provider
from financeops.modules.payment.domain.enums import PaymentProvider
from financeops.shared_kernel.idempotency import require_idempotency_key
from financeops.shared_kernel.response import ok

router = APIRouter()


@router.get("/invoices")
async def list_invoices(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    service = InvoiceService(session)
    rows = await service.list_tenant_invoices(tenant_id=user.tenant_id)
    return ok(
        {
            "items": [
                {
                    "id": str(row.id),
                    "status": row.status,
                    "currency": row.currency,
                    "total": str(row.total),
                    "due_date": row.due_date.isoformat(),
                    "paid_at": row.paid_at.isoformat() if row.paid_at else None,
                }
                for row in rows
            ]
        },
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.get("/invoices/{id}")
async def get_invoice(
    request: Request,
    id: str,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    row = (
        await session.execute(
            select(BillingInvoice).where(
                BillingInvoice.tenant_id == user.tenant_id,
                BillingInvoice.id == uuid.UUID(id),
            )
        )
    ).scalar_one()
    return ok(
        {
            "id": str(row.id),
            "status": row.status,
            "currency": row.currency,
            "subtotal": str(row.subtotal),
            "tax": str(row.tax),
            "total": str(row.total),
            "credits_applied": row.credits_applied,
            "line_items": row.line_items,
            "due_date": row.due_date.isoformat(),
            "paid_at": row.paid_at.isoformat() if row.paid_at else None,
            "invoice_pdf_url": row.invoice_pdf_url,
        },
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.post("/invoices/{id}/pay")
async def pay_invoice(
    request: Request,
    id: str,
    body: dict[str, Any],
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
    _: str = Depends(require_idempotency_key),
) -> dict:
    invoice = (
        await session.execute(
            select(BillingInvoice).where(
                BillingInvoice.tenant_id == user.tenant_id,
                BillingInvoice.id == uuid.UUID(id),
            )
        )
    ).scalar_one()
    provider = get_provider(PaymentProvider(body.get("provider", "stripe")))
    payment_result = await provider.pay_invoice(
        invoice_id=invoice.provider_invoice_id,
        payment_method_id=str(body["payment_method_id"]),
    )
    service = InvoiceService(session)
    row = await service.mark_paid(
        tenant_id=user.tenant_id,
        invoice_id=invoice.id,
        payment_result=payment_result,
    )
    await session.flush()
    return ok(
        {
            "invoice_id": str(row.id),
            "status": row.status,
            "provider_result": payment_result.model_dump(mode="json"),
        },
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")
