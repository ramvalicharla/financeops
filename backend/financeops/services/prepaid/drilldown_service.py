from __future__ import annotations

import uuid
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import NotFoundError
from financeops.db.models.prepaid import (
    Prepaid,
    PrepaidAmortizationSchedule,
    PrepaidJournalEntry,
    PrepaidRun,
)


def _correlation_uuid(value: str | None) -> UUID:
    if not value:
        return uuid.UUID("00000000-0000-0000-0000-000000000000")
    try:
        return UUID(str(value))
    except ValueError:
        return uuid.uuid5(uuid.NAMESPACE_URL, str(value))


def _decimal_text(value: Decimal) -> str:
    return f"{value:.6f}"


async def _get_run_or_raise(session: AsyncSession, *, tenant_id: UUID, run_id: UUID) -> PrepaidRun:
    run_result = await session.execute(
        select(PrepaidRun).where(
            PrepaidRun.tenant_id == tenant_id,
            PrepaidRun.id == run_id,
        )
    )
    run = run_result.scalar_one_or_none()
    if run is None:
        raise NotFoundError("Prepaid run not found")
    return run


async def get_prepaid_drill(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
    prepaid_id: UUID,
) -> dict:
    await _get_run_or_raise(session, tenant_id=tenant_id, run_id=run_id)

    prepaid_result = await session.execute(
        select(Prepaid).where(
            Prepaid.tenant_id == tenant_id,
            Prepaid.id == prepaid_id,
        )
    )
    prepaid = prepaid_result.scalar_one_or_none()
    if prepaid is None:
        raise NotFoundError("Prepaid record not found")

    schedule_ids = (
        await session.execute(
            select(PrepaidAmortizationSchedule.id)
            .where(
                PrepaidAmortizationSchedule.tenant_id == tenant_id,
                PrepaidAmortizationSchedule.run_id == run_id,
                PrepaidAmortizationSchedule.prepaid_id == prepaid_id,
            )
            .order_by(
                PrepaidAmortizationSchedule.amortization_date,
                PrepaidAmortizationSchedule.period_seq,
                PrepaidAmortizationSchedule.id,
            )
        )
    ).scalars().all()

    return {
        "id": prepaid.id,
        "parent_reference_id": prepaid.parent_reference_id,
        "source_reference_id": prepaid.source_reference_id,
        "correlation_id": _correlation_uuid(prepaid.correlation_id),
        "child_ids": list(schedule_ids),
        "metadata": {
            "run_id": str(run_id),
            "source_expense_reference": prepaid.source_expense_reference,
            "period_frequency": prepaid.period_frequency,
        },
        "prepaid_code": prepaid.prepaid_code,
        "prepaid_currency": prepaid.prepaid_currency,
        "reporting_currency": prepaid.reporting_currency,
        "base_amount_contract_currency": _decimal_text(prepaid.base_amount_contract_currency),
        "pattern_type": prepaid.pattern_type,
        "rate_mode": prepaid.rate_mode,
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
        select(PrepaidAmortizationSchedule).where(
            PrepaidAmortizationSchedule.tenant_id == tenant_id,
            PrepaidAmortizationSchedule.run_id == run_id,
            PrepaidAmortizationSchedule.id == schedule_id,
        )
    )
    schedule = schedule_result.scalar_one_or_none()
    if schedule is None:
        raise NotFoundError("Prepaid schedule line not found")

    child_ids = [schedule.source_reference_id] if schedule.source_reference_id is not None else []
    return {
        "id": schedule.id,
        "parent_reference_id": schedule.parent_reference_id,
        "source_reference_id": schedule.source_reference_id,
        "correlation_id": _correlation_uuid(schedule.correlation_id),
        "child_ids": child_ids,
        "metadata": {
            "run_id": str(run_id),
            "source_expense_reference": schedule.source_expense_reference,
            "schedule_status": schedule.schedule_status,
        },
        "prepaid_id": schedule.prepaid_id,
        "period_seq": schedule.period_seq,
        "amortization_date": schedule.amortization_date,
        "schedule_version_token": schedule.schedule_version_token,
        "amortized_amount_reporting_currency": _decimal_text(
            schedule.amortized_amount_reporting_currency
        ),
        "cumulative_amortized_reporting_currency": _decimal_text(
            schedule.cumulative_amortized_reporting_currency
        ),
        "fx_rate_used": _decimal_text(schedule.fx_rate_used),
        "fx_rate_date": schedule.fx_rate_date,
        "fx_rate_source": schedule.fx_rate_source,
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
        select(PrepaidJournalEntry).where(
            PrepaidJournalEntry.tenant_id == tenant_id,
            PrepaidJournalEntry.run_id == run_id,
            PrepaidJournalEntry.id == journal_id,
        )
    )
    journal = journal_result.scalar_one_or_none()
    if journal is None:
        raise NotFoundError("Prepaid journal entry not found")

    return {
        "id": journal.id,
        "parent_reference_id": journal.parent_reference_id,
        "source_reference_id": journal.source_reference_id,
        "correlation_id": _correlation_uuid(journal.correlation_id),
        "child_ids": [journal.schedule_id],
        "metadata": {
            "run_id": str(run_id),
            "source_expense_reference": journal.source_expense_reference,
        },
        "prepaid_id": journal.prepaid_id,
        "schedule_id": journal.schedule_id,
        "journal_reference": journal.journal_reference,
        "entry_date": journal.entry_date,
        "debit_account": journal.debit_account,
        "credit_account": journal.credit_account,
        "amount_reporting_currency": _decimal_text(journal.amount_reporting_currency),
    }
