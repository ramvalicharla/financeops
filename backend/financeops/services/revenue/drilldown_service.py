from __future__ import annotations

import uuid
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import NotFoundError
from financeops.db.models.revenue import (
    RevenueContract,
    RevenueContractLineItem,
    RevenueJournalEntry,
    RevenuePerformanceObligation,
    RevenueRun,
    RevenueSchedule,
)


def _correlation_uuid(value: str | None) -> UUID:
    if not value:
        return uuid.UUID("00000000-0000-0000-0000-000000000000")
    try:
        return UUID(str(value))
    except ValueError:
        return uuid.uuid5(uuid.NAMESPACE_URL, str(value))


async def _get_run_or_raise(session: AsyncSession, *, tenant_id: UUID, run_id: UUID) -> RevenueRun:
    run_result = await session.execute(
        select(RevenueRun).where(
            RevenueRun.tenant_id == tenant_id,
            RevenueRun.id == run_id,
        )
    )
    run = run_result.scalar_one_or_none()
    if run is None:
        raise NotFoundError("Revenue run not found")
    return run


def _decimal_text(value: Decimal) -> str:
    return f"{value:.6f}"


async def get_contract_drill(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
    contract_id: UUID,
) -> dict:
    await _get_run_or_raise(session, tenant_id=tenant_id, run_id=run_id)
    contract_result = await session.execute(
        select(RevenueContract).where(
            RevenueContract.tenant_id == tenant_id,
            RevenueContract.id == contract_id,
        )
    )
    contract = contract_result.scalar_one_or_none()
    if contract is None:
        raise NotFoundError("Revenue contract not found")

    obligation_rows = (
        await session.execute(
            select(RevenuePerformanceObligation.id)
            .where(
                RevenuePerformanceObligation.tenant_id == tenant_id,
                RevenuePerformanceObligation.contract_id == contract_id,
            )
            .order_by(RevenuePerformanceObligation.obligation_code, RevenuePerformanceObligation.id)
        )
    ).scalars().all()

    return {
        "id": contract.id,
        "parent_reference_id": contract.supersedes_id,
        "source_reference_id": None,
        "correlation_id": _correlation_uuid(contract.correlation_id),
        "child_ids": list(obligation_rows),
        "metadata": {
            "run_id": str(run_id),
            "source_contract_reference": contract.source_contract_reference,
            "policy_code": contract.policy_code,
            "policy_version": contract.policy_version,
        },
        "contract_number": contract.contract_number,
        "customer_id": contract.customer_id,
        "contract_currency": contract.contract_currency,
        "total_contract_value": _decimal_text(contract.total_contract_value),
    }


async def get_obligation_drill(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
    obligation_id: UUID,
) -> dict:
    await _get_run_or_raise(session, tenant_id=tenant_id, run_id=run_id)
    obligation_result = await session.execute(
        select(RevenuePerformanceObligation).where(
            RevenuePerformanceObligation.tenant_id == tenant_id,
            RevenuePerformanceObligation.id == obligation_id,
        )
    )
    obligation = obligation_result.scalar_one_or_none()
    if obligation is None:
        raise NotFoundError("Revenue obligation not found")

    line_ids = (
        await session.execute(
            select(RevenueContractLineItem.id)
            .where(
                RevenueContractLineItem.tenant_id == tenant_id,
                RevenueContractLineItem.obligation_id == obligation_id,
            )
            .order_by(RevenueContractLineItem.line_code, RevenueContractLineItem.id)
        )
    ).scalars().all()

    return {
        "id": obligation.id,
        "parent_reference_id": obligation.parent_reference_id,
        "source_reference_id": obligation.source_reference_id,
        "correlation_id": _correlation_uuid(obligation.correlation_id),
        "child_ids": list(line_ids),
        "metadata": {
            "run_id": str(run_id),
            "source_contract_reference": obligation.source_contract_reference,
            "allocation_basis": obligation.allocation_basis,
        },
        "contract_id": obligation.contract_id,
        "obligation_code": obligation.obligation_code,
        "recognition_method": obligation.recognition_method,
        "standalone_selling_price": _decimal_text(obligation.standalone_selling_price),
    }


async def get_schedule_drill(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
    schedule_id: UUID,
) -> dict:
    await _get_run_or_raise(session, tenant_id=tenant_id, run_id=run_id)
    schedule_result = await session.execute(
        select(RevenueSchedule).where(
            RevenueSchedule.tenant_id == tenant_id,
            RevenueSchedule.run_id == run_id,
            RevenueSchedule.id == schedule_id,
        )
    )
    schedule = schedule_result.scalar_one_or_none()
    if schedule is None:
        raise NotFoundError("Revenue schedule not found")

    return {
        "id": schedule.id,
        "parent_reference_id": schedule.parent_reference_id,
        "source_reference_id": schedule.source_reference_id,
        "correlation_id": _correlation_uuid(schedule.correlation_id),
        "child_ids": [schedule.contract_line_item_id],
        "metadata": {
            "run_id": str(run_id),
            "source_contract_reference": schedule.source_contract_reference,
            "schedule_status": schedule.schedule_status,
            "fx_rate_used": _decimal_text(schedule.fx_rate_used),
        },
        "contract_id": schedule.contract_id,
        "obligation_id": schedule.obligation_id,
        "contract_line_item_id": schedule.contract_line_item_id,
        "period_seq": schedule.period_seq,
        "recognition_date": schedule.recognition_date,
        "schedule_version_token": schedule.schedule_version_token,
        "recognition_method": schedule.recognition_method,
        "recognized_amount_reporting_currency": _decimal_text(
            schedule.recognized_amount_reporting_currency
        ),
        "cumulative_recognized_reporting_currency": _decimal_text(
            schedule.cumulative_recognized_reporting_currency
        ),
    }


async def get_journal_drill(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
    journal_id: UUID,
) -> dict:
    await _get_run_or_raise(session, tenant_id=tenant_id, run_id=run_id)
    journal_result = await session.execute(
        select(RevenueJournalEntry).where(
            RevenueJournalEntry.tenant_id == tenant_id,
            RevenueJournalEntry.run_id == run_id,
            RevenueJournalEntry.id == journal_id,
        )
    )
    journal = journal_result.scalar_one_or_none()
    if journal is None:
        raise NotFoundError("Revenue journal entry not found")

    return {
        "id": journal.id,
        "parent_reference_id": journal.parent_reference_id,
        "source_reference_id": journal.source_reference_id,
        "correlation_id": _correlation_uuid(journal.correlation_id),
        "child_ids": [journal.schedule_id],
        "metadata": {
            "run_id": str(run_id),
            "source_contract_reference": journal.source_contract_reference,
        },
        "schedule_id": journal.schedule_id,
        "journal_reference": journal.journal_reference,
        "entry_date": journal.entry_date,
        "debit_account": journal.debit_account,
        "credit_account": journal.credit_account,
        "amount_reporting_currency": _decimal_text(journal.amount_reporting_currency),
    }

