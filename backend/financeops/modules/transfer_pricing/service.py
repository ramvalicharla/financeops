from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.modules.budgeting.models import BudgetLineItem
from financeops.modules.transfer_pricing.models import ICTransaction, TPConfig, TransferPricingDoc

_MONEY = Decimal("0.01")


def _money(value: Decimal | int | str | None) -> Decimal:
    if value is None:
        return Decimal("0.00")
    return Decimal(str(value)).quantize(_MONEY, rounding=ROUND_HALF_UP)


async def get_or_create_config(session: AsyncSession, tenant_id: uuid.UUID) -> TPConfig:
    row = (
        await session.execute(select(TPConfig).where(TPConfig.tenant_id == tenant_id))
    ).scalar_one_or_none()
    if row is not None:
        return row
    now = datetime.now(UTC)
    row = TPConfig(
        tenant_id=tenant_id,
        consolidated_revenue_threshold=Decimal("50000000.00"),
        international_transactions_exist=False,
        specified_domestic_transactions_exist=False,
        applicable_methods=[],
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    await session.flush()
    return row


async def check_3ceb_applicability(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    fiscal_year: int,
) -> dict:
    config = await get_or_create_config(session, tenant_id)
    txns = (
        await session.execute(
            select(ICTransaction).where(ICTransaction.tenant_id == tenant_id, ICTransaction.fiscal_year == fiscal_year)
        )
    ).scalars().all()

    international_value = sum((_money(t.transaction_amount_inr) for t in txns if t.is_international), Decimal("0.00")).quantize(_MONEY, rounding=ROUND_HALF_UP)
    domestic_value = sum((_money(t.transaction_amount_inr) for t in txns if not t.is_international), Decimal("0.00")).quantize(_MONEY, rounding=ROUND_HALF_UP)

    consolidated_revenue = (
        await session.execute(
            select(func.coalesce(func.sum(BudgetLineItem.annual_total), 0)).where(BudgetLineItem.tenant_id == tenant_id)
        )
    ).scalar_one()
    revenue = _money(consolidated_revenue)

    required = False
    reason = "No qualifying transactions"
    if international_value > Decimal("0.00") or config.international_transactions_exist:
        required = True
        reason = "International transactions exist"
    elif (domestic_value > Decimal("0.00") or config.specified_domestic_transactions_exist) and revenue > _money(config.consolidated_revenue_threshold):
        required = True
        reason = "Specified domestic transactions above threshold"

    return {
        "is_required": required,
        "reason": reason,
        "international_transaction_value": international_value,
        "domestic_transaction_value": domestic_value,
    }


async def compute_arm_length_adjustment(
    transaction_amount: Decimal,
    arm_length_price: Decimal,
    actual_price: Decimal,
) -> Decimal:
    del transaction_amount
    return (_money(arm_length_price) - _money(actual_price)).quantize(_MONEY, rounding=ROUND_HALF_UP)


async def add_transaction(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    fiscal_year: int,
    transaction_type: str,
    related_party_name: str,
    related_party_country: str,
    transaction_amount: Decimal,
    currency: str,
    pricing_method: str,
    is_international: bool,
    arm_length_price: Decimal | None = None,
    actual_price: Decimal | None = None,
    description: str | None = None,
) -> ICTransaction:
    amount = _money(transaction_amount)
    amount_inr = amount
    adjustment = Decimal("0.00")
    if arm_length_price is not None and actual_price is not None:
        adjustment = await compute_arm_length_adjustment(amount, arm_length_price, actual_price)

    row = ICTransaction(
        tenant_id=tenant_id,
        fiscal_year=fiscal_year,
        transaction_type=transaction_type,
        related_party_name=related_party_name,
        related_party_country=related_party_country,
        transaction_amount=amount,
        currency=currency,
        transaction_amount_inr=amount_inr,
        pricing_method=pricing_method,
        arm_length_price=_money(arm_length_price) if arm_length_price is not None else None,
        actual_price=_money(actual_price) if actual_price is not None else None,
        adjustment_required=adjustment,
        is_international=is_international,
        description=description,
    )
    session.add(row)

    config = await get_or_create_config(session, tenant_id)
    if is_international:
        config.international_transactions_exist = True
    else:
        config.specified_domestic_transactions_exist = True
    config.updated_at = datetime.now(UTC)

    await session.flush()
    return row


async def generate_form_3ceb(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    fiscal_year: int,
    created_by: uuid.UUID,
) -> TransferPricingDoc:
    txns = (
        await session.execute(
            select(ICTransaction)
            .where(ICTransaction.tenant_id == tenant_id, ICTransaction.fiscal_year == fiscal_year)
            .order_by(ICTransaction.created_at, ICTransaction.id)
        )
    ).scalars().all()

    version = int(
        (
            await session.execute(
                select(func.coalesce(func.max(TransferPricingDoc.version), 0)).where(
                    TransferPricingDoc.tenant_id == tenant_id,
                    TransferPricingDoc.fiscal_year == fiscal_year,
                    TransferPricingDoc.document_type == "form_3ceb",
                )
            )
        ).scalar_one()
    ) + 1

    content = {
        "part_a": {
            "tenant_id": str(tenant_id),
            "fiscal_year": fiscal_year,
            "generated_at": datetime.now(UTC).isoformat(),
        },
        "part_b": [
            {
                "transaction_id": str(row.id),
                "type": row.transaction_type,
                "related_party_name": row.related_party_name,
                "country": row.related_party_country,
                "transaction_amount_inr": str(row.transaction_amount_inr),
                "method": row.pricing_method,
                "adjustment_required": str(row.adjustment_required),
            }
            for row in txns
            if row.is_international
        ],
        "part_c": [
            {
                "transaction_id": str(row.id),
                "type": row.transaction_type,
                "related_party_name": row.related_party_name,
                "transaction_amount_inr": str(row.transaction_amount_inr),
                "method": row.pricing_method,
            }
            for row in txns
            if not row.is_international
        ],
        "part_d": {
            "declaration": "We certify transfer pricing documentation is prepared per applicable law.",
        },
    }

    row = TransferPricingDoc(
        tenant_id=tenant_id,
        fiscal_year=fiscal_year,
        document_type="form_3ceb",
        version=version,
        content=content,
        ai_narrative="Form 3CEB generated from intercompany transaction registry.",
        status="draft",
        created_by=created_by,
    )
    session.add(row)
    await session.flush()
    return row


async def list_transactions(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    fiscal_year: int | None = None,
    skip: int = 0,
    limit: int = 100,
    offset: int | None = None,
) -> dict:
    effective_skip = offset if offset is not None else skip
    bounded_limit = max(1, min(limit, 1000))
    stmt = select(ICTransaction).where(ICTransaction.tenant_id == tenant_id)
    if fiscal_year is not None:
        stmt = stmt.where(ICTransaction.fiscal_year == fiscal_year)

    total = int((await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one())
    rows = (
        await session.execute(
            stmt.order_by(desc(ICTransaction.created_at), desc(ICTransaction.id))
            .limit(bounded_limit)
            .offset(effective_skip)
        )
    ).scalars().all()
    return {"data": rows, "total": total, "limit": bounded_limit, "offset": effective_skip}


async def list_documents(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
    offset: int | None = None,
) -> dict:
    effective_skip = offset if offset is not None else skip
    bounded_limit = max(1, min(limit, 1000))
    stmt = select(TransferPricingDoc).where(TransferPricingDoc.tenant_id == tenant_id)
    total = int((await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one())
    rows = (
        await session.execute(
            stmt.order_by(desc(TransferPricingDoc.created_at), desc(TransferPricingDoc.id))
            .limit(bounded_limit)
            .offset(effective_skip)
        )
    ).scalars().all()
    return {"data": rows, "total": total, "limit": bounded_limit, "offset": effective_skip}


__all__ = [
    "check_3ceb_applicability",
    "generate_form_3ceb",
    "compute_arm_length_adjustment",
    "add_transaction",
    "list_transactions",
    "list_documents",
    "get_or_create_config",
]
