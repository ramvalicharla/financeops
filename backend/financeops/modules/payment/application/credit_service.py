from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import InsufficientCreditsError
from financeops.db.models.payment import BillingPlan, CreditLedger, CreditTopUp
from financeops.modules.payment.domain.enums import CreditTransactionType
from financeops.modules.payment.domain.schemas import PaymentProviderResult
from financeops.services.audit_writer import AuditWriter


class CreditService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def allocate_plan_credits(
        self,
        *,
        tenant_id: uuid.UUID,
        plan_id: uuid.UUID,
        period_start: date,
        created_by: uuid.UUID,
    ) -> CreditLedger:
        plan = (
            await self._session.execute(
                select(BillingPlan).where(BillingPlan.tenant_id == tenant_id, BillingPlan.id == plan_id)
            )
        ).scalar_one()
        current_balance = await self.get_balance(tenant_id=tenant_id)
        next_balance = current_balance + int(plan.included_credits)
        expires_at = datetime.combine(period_start, datetime.min.time(), tzinfo=UTC)
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=CreditLedger,
            tenant_id=tenant_id,
            record_data={
                "transaction_type": CreditTransactionType.PLAN_ALLOCATION.value,
                "credits_delta": str(plan.included_credits),
                "plan_id": str(plan_id),
            },
            values={
                "transaction_type": CreditTransactionType.PLAN_ALLOCATION.value,
                "credits_delta": int(plan.included_credits),
                "credits_balance_after": next_balance,
                "reference_id": str(plan_id),
                "reference_type": "billing_plan",
                "description": "Plan credit allocation",
                "expires_at": expires_at,
            },
        )

    async def purchase_top_up(
        self,
        *,
        tenant_id: uuid.UUID,
        credits: int,
        payment_result: PaymentProviderResult,
        amount_charged: Decimal,
        currency: str,
        provider: str,
        created_by: uuid.UUID,
    ) -> CreditLedger:
        if not payment_result.success:
            raise InsufficientCreditsError("Top-up payment failed")
        current_balance = await self.get_balance(tenant_id=tenant_id)
        next_balance = current_balance + credits

        top_up_row = await AuditWriter.insert_financial_record(
            self._session,
            model_class=CreditTopUp,
            tenant_id=tenant_id,
            record_data={
                "credits_purchased": str(credits),
                "provider_payment_id": payment_result.provider_id or "",
            },
            values={
                "credits_purchased": credits,
                "amount_charged": amount_charged,
                "currency": currency.upper(),
                "provider": provider,
                "provider_payment_id": payment_result.provider_id or "",
                "invoice_id": None,
                "status": "completed",
            },
        )

        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=CreditLedger,
            tenant_id=tenant_id,
            record_data={
                "transaction_type": CreditTransactionType.TOP_UP_PURCHASE.value,
                "credits_delta": str(credits),
                "top_up_id": str(top_up_row.id),
            },
            values={
                "transaction_type": CreditTransactionType.TOP_UP_PURCHASE.value,
                "credits_delta": credits,
                "credits_balance_after": next_balance,
                "reference_id": str(top_up_row.id),
                "reference_type": "credit_top_up",
                "description": "Top-up credit purchase",
                "expires_at": None,
            },
        )

    async def consume_credits(
        self,
        *,
        tenant_id: uuid.UUID,
        credits: int,
        reference_id: str,
        reference_type: str,
        created_by: uuid.UUID,
    ) -> CreditLedger:
        latest = (
            await self._session.execute(
                select(CreditLedger)
                .where(CreditLedger.tenant_id == tenant_id)
                .order_by(CreditLedger.created_at.desc(), CreditLedger.id.desc())
                .limit(1)
                .with_for_update()
            )
        ).scalar_one_or_none()

        current_balance = latest.credits_balance_after if latest is not None else 0
        if current_balance < credits:
            raise InsufficientCreditsError()
        next_balance = current_balance - credits

        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=CreditLedger,
            tenant_id=tenant_id,
            record_data={
                "transaction_type": CreditTransactionType.CONSUMPTION.value,
                "credits_delta": str(-credits),
                "reference_id": reference_id,
            },
            values={
                "transaction_type": CreditTransactionType.CONSUMPTION.value,
                "credits_delta": -credits,
                "credits_balance_after": next_balance,
                "reference_id": reference_id,
                "reference_type": reference_type,
                "description": "Credit consumption",
                "expires_at": None,
            },
        )

    async def get_balance(self, *, tenant_id: uuid.UUID) -> int:
        now_ts = datetime.now(UTC)
        total = await self._session.scalar(
            select(func.coalesce(func.sum(CreditLedger.credits_delta), 0)).where(
                CreditLedger.tenant_id == tenant_id,
                (CreditLedger.expires_at.is_(None)) | (CreditLedger.expires_at >= now_ts),
            )
        )
        return int(total or 0)
