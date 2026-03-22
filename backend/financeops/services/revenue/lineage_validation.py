from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.revenue import (
    RevenueContract,
    RevenueContractLineItem,
    RevenueJournalEntry,
    RevenuePerformanceObligation,
    RevenueSchedule,
)
from financeops.services.accounting_common.run_validation import LineageValidationResult


async def validate_revenue_lineage(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
) -> LineageValidationResult:
    missing_schedule_line_links = int(
        await session.scalar(
            select(func.count())
            .select_from(RevenueSchedule)
            .outerjoin(
                RevenueContractLineItem,
                RevenueSchedule.contract_line_item_id == RevenueContractLineItem.id,
            )
            .where(
                RevenueSchedule.tenant_id == tenant_id,
                RevenueSchedule.run_id == run_id,
                RevenueContractLineItem.id.is_(None),
            )
        )
        or 0
    )

    missing_line_item_contract_links = int(
        await session.scalar(
            select(func.count())
            .select_from(RevenueContractLineItem)
            .outerjoin(
                RevenueContract,
                RevenueContractLineItem.contract_id == RevenueContract.id,
            )
            .where(
                RevenueContractLineItem.tenant_id == tenant_id,
                RevenueContractLineItem.correlation_id.in_(
                    select(RevenueSchedule.correlation_id).where(
                        RevenueSchedule.tenant_id == tenant_id,
                        RevenueSchedule.run_id == run_id,
                    )
                ),
                RevenueContract.id.is_(None),
            )
        )
        or 0
    )

    missing_line_item_obligation_links = int(
        await session.scalar(
            select(func.count())
            .select_from(RevenueContractLineItem)
            .outerjoin(
                RevenuePerformanceObligation,
                RevenueContractLineItem.obligation_id == RevenuePerformanceObligation.id,
            )
            .where(
                RevenueContractLineItem.tenant_id == tenant_id,
                RevenueContractLineItem.obligation_id.is_not(None),
                RevenueContractLineItem.correlation_id.in_(
                    select(RevenueSchedule.correlation_id).where(
                        RevenueSchedule.tenant_id == tenant_id,
                        RevenueSchedule.run_id == run_id,
                    )
                ),
                RevenuePerformanceObligation.id.is_(None),
            )
        )
        or 0
    )

    missing_journal_schedule_links = int(
        await session.scalar(
            select(func.count())
            .select_from(RevenueJournalEntry)
            .outerjoin(
                RevenueSchedule,
                RevenueJournalEntry.schedule_id == RevenueSchedule.id,
            )
            .where(
                RevenueJournalEntry.tenant_id == tenant_id,
                RevenueJournalEntry.run_id == run_id,
                RevenueSchedule.id.is_(None),
            )
        )
        or 0
    )

    details = {
        "missing_schedule_line_links": missing_schedule_line_links,
        "missing_line_item_contract_links": missing_line_item_contract_links,
        "missing_line_item_obligation_links": missing_line_item_obligation_links,
        "missing_journal_schedule_links": missing_journal_schedule_links,
    }
    is_complete = all(value == 0 for value in details.values())
    return LineageValidationResult(is_complete=is_complete, details=details)

