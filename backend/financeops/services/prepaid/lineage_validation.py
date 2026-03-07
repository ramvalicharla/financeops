from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.prepaid import (
    Prepaid,
    PrepaidAmortizationSchedule,
    PrepaidJournalEntry,
)
from financeops.services.accounting_common.run_validation import LineageValidationResult


async def validate_prepaid_lineage(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
) -> LineageValidationResult:
    missing_schedule_prepaid_links = int(
        await session.scalar(
            select(func.count())
            .select_from(PrepaidAmortizationSchedule)
            .outerjoin(Prepaid, PrepaidAmortizationSchedule.prepaid_id == Prepaid.id)
            .where(
                PrepaidAmortizationSchedule.tenant_id == tenant_id,
                PrepaidAmortizationSchedule.run_id == run_id,
                Prepaid.id.is_(None),
            )
        )
        or 0
    )

    missing_schedule_source_links = int(
        await session.scalar(
            select(func.count())
            .select_from(PrepaidAmortizationSchedule)
            .where(
                PrepaidAmortizationSchedule.tenant_id == tenant_id,
                PrepaidAmortizationSchedule.run_id == run_id,
                (
                    PrepaidAmortizationSchedule.source_reference_id.is_(None)
                    | (PrepaidAmortizationSchedule.source_expense_reference == "")
                ),
            )
        )
        or 0
    )

    missing_journal_schedule_links = int(
        await session.scalar(
            select(func.count())
            .select_from(PrepaidJournalEntry)
            .outerjoin(
                PrepaidAmortizationSchedule,
                PrepaidJournalEntry.schedule_id == PrepaidAmortizationSchedule.id,
            )
            .where(
                PrepaidJournalEntry.tenant_id == tenant_id,
                PrepaidJournalEntry.run_id == run_id,
                PrepaidAmortizationSchedule.id.is_(None),
            )
        )
        or 0
    )

    details = {
        "missing_schedule_prepaid_links": missing_schedule_prepaid_links,
        "missing_schedule_source_links": missing_schedule_source_links,
        "missing_journal_schedule_links": missing_journal_schedule_links,
    }
    complete = all(value == 0 for value in details.values())
    return LineageValidationResult(is_complete=complete, details=details)
