from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.modules.expense_management.models import ExpenseClaim
from financeops.modules.search.service import upsert_index_entry


async def index_expense(session: AsyncSession, expense_claim: ExpenseClaim) -> None:
    await upsert_index_entry(
        session,
        tenant_id=expense_claim.tenant_id,
        entity_type="expense_claim",
        entity_id=expense_claim.id,
        title=f"{expense_claim.vendor_name} - INR {expense_claim.amount}",
        subtitle=expense_claim.description,
        body=expense_claim.justification,
        url=f"/expenses/{expense_claim.id}",
        metadata={
            "amount": str(expense_claim.amount),
            "status": expense_claim.status,
            "category": expense_claim.category,
        },
    )


async def reindex_all_expenses(session: AsyncSession, tenant_id: uuid.UUID) -> int:
    rows = (
        await session.execute(
            select(ExpenseClaim).where(ExpenseClaim.tenant_id == tenant_id)
        )
    ).scalars().all()
    for row in rows:
        await index_expense(session, row)
    return len(rows)


__all__ = ["index_expense", "reindex_all_expenses"]

