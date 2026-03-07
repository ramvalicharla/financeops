from __future__ import annotations

import uuid
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import NotFoundError
from financeops.db.models.lease import (
    Lease,
    LeaseJournalEntry,
    LeaseLiabilitySchedule,
    LeasePayment,
    LeaseRouSchedule,
    LeaseRun,
)


def _correlation_uuid(value: str | None) -> UUID:
    if not value:
        return uuid.UUID("00000000-0000-0000-0000-000000000000")
    try:
        return UUID(str(value))
    except ValueError:
        return uuid.uuid5(uuid.NAMESPACE_URL, str(value))


async def _get_run_or_raise(session: AsyncSession, *, tenant_id: UUID, run_id: UUID) -> LeaseRun:
    run_result = await session.execute(
        select(LeaseRun).where(
            LeaseRun.tenant_id == tenant_id,
            LeaseRun.id == run_id,
        )
    )
    run = run_result.scalar_one_or_none()
    if run is None:
        raise NotFoundError("Lease run not found")
    return run


def _decimal_text(value: Decimal) -> str:
    return f"{value:.6f}"


async def get_lease_drill(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
    lease_id: UUID,
) -> dict:
    await _get_run_or_raise(session, tenant_id=tenant_id, run_id=run_id)
    lease_result = await session.execute(
        select(Lease).where(
            Lease.tenant_id == tenant_id,
            Lease.id == lease_id,
        )
    )
    lease = lease_result.scalar_one_or_none()
    if lease is None:
        raise NotFoundError("Lease not found")

    payment_ids = (
        await session.execute(
            select(LeasePayment.id)
            .where(
                LeasePayment.tenant_id == tenant_id,
                LeasePayment.lease_id == lease_id,
            )
            .order_by(LeasePayment.payment_sequence, LeasePayment.payment_date, LeasePayment.id)
        )
    ).scalars().all()

    return {
        "id": lease.id,
        "parent_reference_id": lease.parent_reference_id,
        "source_reference_id": lease.source_reference_id,
        "correlation_id": _correlation_uuid(lease.correlation_id),
        "child_ids": list(payment_ids),
        "metadata": {
            "run_id": str(run_id),
            "source_lease_reference": lease.source_lease_reference,
            "policy_code": lease.policy_code,
            "policy_version": lease.policy_version,
        },
        "lease_number": lease.lease_number,
        "lease_currency": lease.lease_currency,
        "initial_discount_rate": _decimal_text(lease.initial_discount_rate),
        "payment_frequency": lease.payment_frequency,
    }


async def get_payment_drill(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
    payment_id: UUID,
) -> dict:
    await _get_run_or_raise(session, tenant_id=tenant_id, run_id=run_id)
    payment_result = await session.execute(
        select(LeasePayment).where(
            LeasePayment.tenant_id == tenant_id,
            LeasePayment.id == payment_id,
        )
    )
    payment = payment_result.scalar_one_or_none()
    if payment is None:
        raise NotFoundError("Lease payment not found")

    liability_line_ids = (
        await session.execute(
            select(LeaseLiabilitySchedule.id)
            .where(
                LeaseLiabilitySchedule.tenant_id == tenant_id,
                LeaseLiabilitySchedule.run_id == run_id,
                LeaseLiabilitySchedule.payment_id == payment_id,
            )
            .order_by(LeaseLiabilitySchedule.schedule_date, LeaseLiabilitySchedule.id)
        )
    ).scalars().all()

    return {
        "id": payment.id,
        "parent_reference_id": payment.parent_reference_id,
        "source_reference_id": payment.source_reference_id,
        "correlation_id": _correlation_uuid(payment.correlation_id),
        "child_ids": list(liability_line_ids),
        "metadata": {
            "run_id": str(run_id),
            "source_lease_reference": payment.source_lease_reference,
        },
        "lease_id": payment.lease_id,
        "payment_date": payment.payment_date,
        "payment_amount_lease_currency": _decimal_text(payment.payment_amount_lease_currency),
        "payment_type": payment.payment_type,
        "payment_sequence": payment.payment_sequence,
    }


async def get_liability_drill(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
    line_id: UUID,
) -> dict:
    await _get_run_or_raise(session, tenant_id=tenant_id, run_id=run_id)
    result = await session.execute(
        select(LeaseLiabilitySchedule).where(
            LeaseLiabilitySchedule.tenant_id == tenant_id,
            LeaseLiabilitySchedule.run_id == run_id,
            LeaseLiabilitySchedule.id == line_id,
        )
    )
    line = result.scalar_one_or_none()
    if line is None:
        raise NotFoundError("Lease liability schedule line not found")

    child_ids: list[UUID] = []
    if line.payment_id is not None:
        child_ids.append(line.payment_id)

    return {
        "id": line.id,
        "parent_reference_id": line.parent_reference_id,
        "source_reference_id": line.source_reference_id,
        "correlation_id": _correlation_uuid(line.correlation_id),
        "child_ids": child_ids,
        "metadata": {
            "run_id": str(run_id),
            "source_lease_reference": line.source_lease_reference,
            "fx_rate_used": _decimal_text(line.fx_rate_used),
        },
        "lease_id": line.lease_id,
        "payment_id": line.payment_id,
        "period_seq": line.period_seq,
        "schedule_date": line.schedule_date,
        "schedule_version_token": line.schedule_version_token,
        "opening_liability_reporting_currency": _decimal_text(line.opening_liability_reporting_currency),
        "interest_expense_reporting_currency": _decimal_text(line.interest_expense_reporting_currency),
        "payment_amount_reporting_currency": _decimal_text(line.payment_amount_reporting_currency),
        "closing_liability_reporting_currency": _decimal_text(line.closing_liability_reporting_currency),
    }


async def get_rou_drill(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
    line_id: UUID,
) -> dict:
    await _get_run_or_raise(session, tenant_id=tenant_id, run_id=run_id)
    result = await session.execute(
        select(LeaseRouSchedule).where(
            LeaseRouSchedule.tenant_id == tenant_id,
            LeaseRouSchedule.run_id == run_id,
            LeaseRouSchedule.id == line_id,
        )
    )
    line = result.scalar_one_or_none()
    if line is None:
        raise NotFoundError("Lease ROU schedule line not found")

    return {
        "id": line.id,
        "parent_reference_id": line.parent_reference_id,
        "source_reference_id": line.source_reference_id,
        "correlation_id": _correlation_uuid(line.correlation_id),
        "child_ids": [line.lease_id],
        "metadata": {
            "run_id": str(run_id),
            "source_lease_reference": line.source_lease_reference,
            "fx_rate_used": _decimal_text(line.fx_rate_used),
        },
        "lease_id": line.lease_id,
        "period_seq": line.period_seq,
        "schedule_date": line.schedule_date,
        "schedule_version_token": line.schedule_version_token,
        "opening_rou_reporting_currency": _decimal_text(line.opening_rou_reporting_currency),
        "amortization_expense_reporting_currency": _decimal_text(line.amortization_expense_reporting_currency),
        "impairment_amount_reporting_currency": _decimal_text(line.impairment_amount_reporting_currency),
        "closing_rou_reporting_currency": _decimal_text(line.closing_rou_reporting_currency),
    }


async def get_journal_drill(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
    journal_id: UUID,
) -> dict:
    await _get_run_or_raise(session, tenant_id=tenant_id, run_id=run_id)
    result = await session.execute(
        select(LeaseJournalEntry).where(
            LeaseJournalEntry.tenant_id == tenant_id,
            LeaseJournalEntry.run_id == run_id,
            LeaseJournalEntry.id == journal_id,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise NotFoundError("Lease journal entry not found")

    child_ids: list[UUID] = []
    if row.liability_schedule_id is not None:
        child_ids.append(row.liability_schedule_id)
    if row.rou_schedule_id is not None:
        child_ids.append(row.rou_schedule_id)

    return {
        "id": row.id,
        "parent_reference_id": row.parent_reference_id,
        "source_reference_id": row.source_reference_id,
        "correlation_id": _correlation_uuid(row.correlation_id),
        "child_ids": child_ids,
        "metadata": {
            "run_id": str(run_id),
            "source_lease_reference": row.source_lease_reference,
        },
        "lease_id": row.lease_id,
        "liability_schedule_id": row.liability_schedule_id,
        "rou_schedule_id": row.rou_schedule_id,
        "journal_reference": row.journal_reference,
        "entry_date": row.entry_date,
        "debit_account": row.debit_account,
        "credit_account": row.credit_account,
        "amount_reporting_currency": _decimal_text(row.amount_reporting_currency),
    }
