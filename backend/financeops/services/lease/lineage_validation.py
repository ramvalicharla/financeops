from __future__ import annotations

from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.lease import (
    Lease,
    LeaseJournalEntry,
    LeaseLiabilitySchedule,
    LeasePayment,
    LeaseRouSchedule,
)
from financeops.services.accounting_common.run_validation import LineageValidationResult


async def validate_lease_lineage(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
) -> LineageValidationResult:
    missing_liability_lease_links = int(
        await session.scalar(
            select(func.count())
            .select_from(LeaseLiabilitySchedule)
            .outerjoin(Lease, LeaseLiabilitySchedule.lease_id == Lease.id)
            .where(
                LeaseLiabilitySchedule.tenant_id == tenant_id,
                LeaseLiabilitySchedule.run_id == run_id,
                Lease.id.is_(None),
            )
        )
        or 0
    )

    missing_liability_payment_links = int(
        await session.scalar(
            select(func.count())
            .select_from(LeaseLiabilitySchedule)
            .outerjoin(LeasePayment, LeaseLiabilitySchedule.payment_id == LeasePayment.id)
            .where(
                LeaseLiabilitySchedule.tenant_id == tenant_id,
                LeaseLiabilitySchedule.run_id == run_id,
                LeaseLiabilitySchedule.payment_id.is_not(None),
                LeasePayment.id.is_(None),
            )
        )
        or 0
    )

    missing_rou_lease_links = int(
        await session.scalar(
            select(func.count())
            .select_from(LeaseRouSchedule)
            .outerjoin(Lease, LeaseRouSchedule.lease_id == Lease.id)
            .where(
                LeaseRouSchedule.tenant_id == tenant_id,
                LeaseRouSchedule.run_id == run_id,
                Lease.id.is_(None),
            )
        )
        or 0
    )

    missing_journal_schedule_links = int(
        await session.scalar(
            select(func.count())
            .select_from(LeaseJournalEntry)
            .outerjoin(
                LeaseLiabilitySchedule,
                and_(
                    LeaseJournalEntry.liability_schedule_id == LeaseLiabilitySchedule.id,
                    LeaseLiabilitySchedule.run_id == run_id,
                ),
            )
            .outerjoin(
                LeaseRouSchedule,
                and_(
                    LeaseJournalEntry.rou_schedule_id == LeaseRouSchedule.id,
                    LeaseRouSchedule.run_id == run_id,
                ),
            )
            .where(
                LeaseJournalEntry.tenant_id == tenant_id,
                LeaseJournalEntry.run_id == run_id,
                LeaseLiabilitySchedule.id.is_(None),
                LeaseRouSchedule.id.is_(None),
            )
        )
        or 0
    )

    details = {
        "missing_liability_lease_links": missing_liability_lease_links,
        "missing_liability_payment_links": missing_liability_payment_links,
        "missing_rou_lease_links": missing_rou_lease_links,
        "missing_journal_schedule_links": missing_journal_schedule_links,
    }
    is_complete = all(value == 0 for value in details.values())
    return LineageValidationResult(is_complete=is_complete, details=details)

