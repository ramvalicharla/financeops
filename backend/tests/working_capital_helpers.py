from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.intent.context import MutationContext, governed_mutation_context
from financeops.db.models.reconciliation import GlEntry
from financeops.modules.working_capital.service import compute_wc_snapshot as _compute_wc_snapshot
from financeops.utils.chain_hash import GENESIS_HASH, compute_chain_hash


def _governed_context() -> MutationContext:
    return MutationContext(
        intent_id=uuid.uuid4(),
        job_id=uuid.uuid4(),
        actor_user_id=None,
        actor_role="finance_leader",
        intent_type="COMPUTE_WORKING_CAPITAL_SNAPSHOT",
    )


async def compute_wc_snapshot(*args, **kwargs):
    with governed_mutation_context(_governed_context()):
        return await _compute_wc_snapshot(*args, **kwargs)


def _period_parts(period: str) -> tuple[int, int]:
    year_text, month_text = period.split("-", 1)
    return int(year_text), int(month_text)


async def seed_gl_entry(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    period: str,
    account_code: str,
    account_name: str,
    debit: Decimal | str = Decimal("0"),
    credit: Decimal | str = Decimal("0"),
    uploaded_by: uuid.UUID,
    entity_id: uuid.UUID | None = None,
    entity_name: str = "WC Test Entity",
    source_ref: str | None = None,
) -> GlEntry:
    period_year, period_month = _period_parts(period)
    debit_amount = Decimal(str(debit))
    credit_amount = Decimal(str(credit))
    entry_ref = source_ref or f"{account_code}-{period}-{uuid.uuid4().hex[:8]}"
    record_data = {
        "tenant_id": str(tenant_id),
        "period": period,
        "account_code": account_code,
        "account_name": account_name,
        "debit_amount": str(debit_amount),
        "credit_amount": str(credit_amount),
        "source_ref": entry_ref,
    }
    entry = GlEntry(
        tenant_id=tenant_id,
        chain_hash=compute_chain_hash(record_data, GENESIS_HASH),
        previous_hash=GENESIS_HASH,
        entity_id=entity_id,
        period_year=period_year,
        period_month=period_month,
        entity_name=entity_name,
        account_code=account_code,
        account_name=account_name,
        debit_amount=debit_amount,
        credit_amount=credit_amount,
        description="Working capital GL seed",
        source_ref=entry_ref,
        currency="INR",
        uploaded_by=uploaded_by,
    )
    session.add(entry)
    await session.flush()
    return entry


async def seed_working_capital_gl_data(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    period: str,
    uploaded_by: uuid.UUID,
    ar: Decimal | str,
    ap: Decimal | str,
    inventory: Decimal | str,
    cash: Decimal | str,
    accrued_liabilities: Decimal | str,
    revenue: Decimal | str,
    cogs: Decimal | str,
    prior_revenue: dict[str, Decimal | str] | None = None,
    entity_id: uuid.UUID | None = None,
    entity_name: str = "WC Test Entity",
) -> None:
    await seed_gl_entry(
        session,
        tenant_id=tenant_id,
        period=period,
        account_code="AR-1000",
        account_name="Trade Receivables",
        debit=ar,
        uploaded_by=uploaded_by,
        entity_id=entity_id,
        entity_name=entity_name,
    )
    await seed_gl_entry(
        session,
        tenant_id=tenant_id,
        period=period,
        account_code="AP-2000",
        account_name="Trade Payables",
        credit=ap,
        uploaded_by=uploaded_by,
        entity_id=entity_id,
        entity_name=entity_name,
    )
    await seed_gl_entry(
        session,
        tenant_id=tenant_id,
        period=period,
        account_code="INV-3000",
        account_name="Inventory",
        debit=inventory,
        uploaded_by=uploaded_by,
        entity_id=entity_id,
        entity_name=entity_name,
    )
    await seed_gl_entry(
        session,
        tenant_id=tenant_id,
        period=period,
        account_code="CASH-4000",
        account_name="Cash and Cash Equivalents",
        debit=cash,
        uploaded_by=uploaded_by,
        entity_id=entity_id,
        entity_name=entity_name,
    )
    await seed_gl_entry(
        session,
        tenant_id=tenant_id,
        period=period,
        account_code="ACC-5000",
        account_name="Accrued Liabilities",
        credit=accrued_liabilities,
        uploaded_by=uploaded_by,
        entity_id=entity_id,
        entity_name=entity_name,
    )
    await seed_gl_entry(
        session,
        tenant_id=tenant_id,
        period=period,
        account_code="REV-6000",
        account_name="Revenue from Operations",
        credit=revenue,
        uploaded_by=uploaded_by,
        entity_id=entity_id,
        entity_name=entity_name,
    )
    await seed_gl_entry(
        session,
        tenant_id=tenant_id,
        period=period,
        account_code="COGS-7000",
        account_name="Cost of Sales",
        debit=cogs,
        uploaded_by=uploaded_by,
        entity_id=entity_id,
        entity_name=entity_name,
    )

    for prior_period, prior_amount in (prior_revenue or {}).items():
        await seed_gl_entry(
            session,
            tenant_id=tenant_id,
            period=prior_period,
            account_code=f"REV-{prior_period.replace('-', '')}",
            account_name="Revenue from Operations",
            credit=prior_amount,
            uploaded_by=uploaded_by,
            entity_id=entity_id,
            entity_name=entity_name,
        )

