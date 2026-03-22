from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import NotFoundError, ValidationError
from financeops.db.models.lease import (
    LeaseJournalEntry,
    LeaseLiabilitySchedule,
    LeaseModification,
    LeaseRouSchedule,
    LeaseRun,
    LeaseRunEvent,
)
from financeops.schemas.lease import LeaseRunRequest
from financeops.services.accounting_common.accounting_errors import AccountingValidationError
from financeops.services.accounting_common.error_codes import (
    INVALID_EVENT_SEQUENCE,
    LINEAGE_INCOMPLETE,
)
from financeops.services.accounting_common.journal_namespace import build_journal_reference
from financeops.services.accounting_common.run_events_base import (
    RUN_EVENT_COMPLETED,
    RUN_EVENT_COMPLETED_WITH_WARNINGS,
    RUN_EVENT_RUNNING,
    TERMINAL_EVENT_TYPES,
)
from financeops.services.accounting_common.run_lifecycle import (
    append_event,
    create_run_header,
    derive_latest_status,
    validate_lineage_before_finalize,
)
from financeops.services.accounting_common.run_signature import build_request_signature
from financeops.services.accounting_common.run_validation import LineageValidationResult
from financeops.services.audit_writer import AuditEvent, AuditWriter
from financeops.services.lease.drilldown_service import (
    get_journal_drill,
    get_lease_drill,
    get_liability_drill,
    get_payment_drill,
    get_rou_drill,
)
from financeops.services.lease.lease_registry import register_leases
from financeops.services.lease.liability_schedule import (
    generate_liability_schedule_rows,
    resolve_lease_fx_rate,
)
from financeops.services.lease.lineage_validation import validate_lease_lineage
from financeops.services.lease.payment_schedule import build_payment_timeline, register_lease_payments
from financeops.services.lease.pv_calculator import calculate_present_value
from financeops.services.lease.remeasurement import apply_lease_modifications
from financeops.services.lease.rou_schedule import generate_rou_schedule_rows

_AUDIT_NAMESPACE = "lease"


async def _get_run_or_raise(session: AsyncSession, *, tenant_id: UUID, run_id: UUID) -> LeaseRun:
    result = await session.execute(
        select(LeaseRun).where(
            LeaseRun.tenant_id == tenant_id,
            LeaseRun.id == run_id,
        )
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise NotFoundError("Lease run not found")
    return run


def _parse_request(configuration_json: dict[str, Any]) -> LeaseRunRequest:
    return LeaseRunRequest.model_validate(configuration_json)


async def _resolve_root_version_token(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
    lease_id: UUID,
) -> str | None:
    first_modification = (
        await session.execute(
            select(LeaseModification)
            .where(
                LeaseModification.tenant_id == tenant_id,
                LeaseModification.run_id == run_id,
                LeaseModification.lease_id == lease_id,
            )
            .order_by(
                LeaseModification.effective_date,
                LeaseModification.created_at,
                LeaseModification.id,
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if first_modification is not None:
        return first_modification.prior_schedule_version_token

    first_schedule = await session.execute(
        select(LeaseLiabilitySchedule.schedule_version_token)
        .where(
            LeaseLiabilitySchedule.tenant_id == tenant_id,
            LeaseLiabilitySchedule.run_id == run_id,
            LeaseLiabilitySchedule.lease_id == lease_id,
        )
        .order_by(
            LeaseLiabilitySchedule.created_at,
            LeaseLiabilitySchedule.period_seq,
            LeaseLiabilitySchedule.id,
        )
        .limit(1)
    )
    return first_schedule.scalar_one_or_none()


async def _resolve_effective_version_token(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
    lease_id: UUID,
    root_schedule_version_token: str,
) -> str:
    latest_modification = (
        await session.execute(
            select(LeaseModification)
            .where(
                LeaseModification.tenant_id == tenant_id,
                LeaseModification.run_id == run_id,
                LeaseModification.lease_id == lease_id,
            )
            .order_by(
                desc(LeaseModification.effective_date),
                desc(LeaseModification.created_at),
                desc(LeaseModification.id),
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if latest_modification is None:
        return root_schedule_version_token
    return latest_modification.new_schedule_version_token


async def create_run(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    initiated_by: UUID,
    request_payload: dict[str, Any],
    correlation_id: str,
) -> dict[str, Any]:
    payload = LeaseRunRequest.model_validate(request_payload)
    signature = build_request_signature(payload.model_dump(mode="json"))
    workflow_id = f"lease-{signature[:24]}"

    result = await create_run_header(
        session,
        run_model=LeaseRun,
        event_model=LeaseRunEvent,
        tenant_id=tenant_id,
        initiated_by=initiated_by,
        request_payload=payload.model_dump(mode="json"),
        workflow_id=workflow_id,
        correlation_id=correlation_id,
        audit_namespace=_AUDIT_NAMESPACE,
    )
    return {
        "run_id": result.run_id,
        "workflow_id": result.workflow_id,
        "request_signature": result.request_signature,
        "status": result.status,
        "created_new": result.created_new,
    }


async def mark_run_running(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
    user_id: UUID,
    correlation_id: str,
) -> LeaseRunEvent:
    return await append_event(
        session,
        event_model=LeaseRunEvent,
        tenant_id=tenant_id,
        run_id=run_id,
        user_id=user_id,
        event_type=RUN_EVENT_RUNNING,
        idempotency_key="stage-running",
        metadata_json=None,
        correlation_id=correlation_id,
        audit_namespace=_AUDIT_NAMESPACE,
    )


async def load_leases_and_payments_for_run(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
    user_id: UUID,
    correlation_id: str,
) -> dict[str, int]:
    run = await _get_run_or_raise(session, tenant_id=tenant_id, run_id=run_id)
    payload = _parse_request(run.configuration_json)

    leases = await register_leases(
        session,
        tenant_id=tenant_id,
        user_id=user_id,
        correlation_id=correlation_id,
        leases=payload.leases,
    )
    payments = await register_lease_payments(
        session,
        tenant_id=tenant_id,
        user_id=user_id,
        correlation_id=correlation_id,
        leases=payload.leases,
        registered_leases=leases,
    )
    return {
        "lease_count": len(leases),
        "payment_count": len(payments),
    }


async def build_payment_timeline_for_run(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
    user_id: UUID,
    correlation_id: str,
) -> dict[str, int]:
    run = await _get_run_or_raise(session, tenant_id=tenant_id, run_id=run_id)
    payload = _parse_request(run.configuration_json)

    leases = await register_leases(
        session,
        tenant_id=tenant_id,
        user_id=user_id,
        correlation_id=correlation_id,
        leases=payload.leases,
    )
    payments = await register_lease_payments(
        session,
        tenant_id=tenant_id,
        user_id=user_id,
        correlation_id=correlation_id,
        leases=payload.leases,
        registered_leases=leases,
    )

    timeline_entries = 0
    for lease in leases:
        timeline_entries += len(build_payment_timeline(lease_id=lease.lease_id, payments=payments))
    return {
        "timeline_count": timeline_entries,
    }


async def calculate_present_value_for_run(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
    user_id: UUID,
    correlation_id: str,
) -> dict[str, str]:
    run = await _get_run_or_raise(session, tenant_id=tenant_id, run_id=run_id)
    payload = _parse_request(run.configuration_json)

    leases = await register_leases(
        session,
        tenant_id=tenant_id,
        user_id=user_id,
        correlation_id=correlation_id,
        leases=payload.leases,
    )
    payments = await register_lease_payments(
        session,
        tenant_id=tenant_id,
        user_id=user_id,
        correlation_id=correlation_id,
        leases=payload.leases,
        registered_leases=leases,
    )

    total_pv_reporting = Decimal("0.000000")
    for lease in leases:
        timeline = build_payment_timeline(lease_id=lease.lease_id, payments=payments)
        commencement_rate = await resolve_lease_fx_rate(
            session,
            tenant_id=tenant_id,
            lease_currency=lease.lease_currency,
            reporting_currency=payload.reporting_currency,
            schedule_date=lease.commencement_date,
            rate_mode=payload.rate_mode,
        )
        pv = calculate_present_value(
            lease_id=lease.lease_id,
            payments=timeline,
            annual_discount_rate=lease.initial_discount_rate,
            payment_frequency=lease.payment_frequency,
            conversion_rate=commencement_rate,
        )
        total_pv_reporting += pv.present_value_reporting_currency

    return {
        "lease_count": str(len(leases)),
        "total_present_value_reporting_currency": f"{total_pv_reporting:.6f}",
    }


async def generate_liability_schedule_for_run(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
    user_id: UUID,
    correlation_id: str,
) -> dict[str, int]:
    run = await _get_run_or_raise(session, tenant_id=tenant_id, run_id=run_id)
    payload = _parse_request(run.configuration_json)

    leases = await register_leases(
        session,
        tenant_id=tenant_id,
        user_id=user_id,
        correlation_id=correlation_id,
        leases=payload.leases,
    )
    payments = await register_lease_payments(
        session,
        tenant_id=tenant_id,
        user_id=user_id,
        correlation_id=correlation_id,
        leases=payload.leases,
        registered_leases=leases,
    )

    generated = await generate_liability_schedule_rows(
        session,
        tenant_id=tenant_id,
        leases=leases,
        payments=payments,
        reporting_currency=payload.reporting_currency,
        rate_mode=payload.rate_mode,
    )

    inserted = 0
    for row in generated.rows:
        existing = await session.execute(
            select(LeaseLiabilitySchedule).where(
                LeaseLiabilitySchedule.tenant_id == tenant_id,
                LeaseLiabilitySchedule.run_id == run_id,
                LeaseLiabilitySchedule.lease_id == row.lease_id,
                LeaseLiabilitySchedule.schedule_date == row.schedule_date,
                LeaseLiabilitySchedule.schedule_version_token == row.schedule_version_token,
                LeaseLiabilitySchedule.period_seq == row.period_seq,
            )
        )
        if existing.scalar_one_or_none() is not None:
            continue

        await AuditWriter.insert_financial_record(
            session,
            model_class=LeaseLiabilitySchedule,
            tenant_id=tenant_id,
            record_data={
                "run_id": str(run_id),
                "lease_id": str(row.lease_id),
                "period_seq": row.period_seq,
                "schedule_date": row.schedule_date.isoformat(),
                "schedule_version_token": row.schedule_version_token,
            },
            values={
                "run_id": run_id,
                "lease_id": row.lease_id,
                "payment_id": row.payment_id,
                "period_seq": row.period_seq,
                "schedule_date": row.schedule_date,
                "period_year": row.period_year,
                "period_month": row.period_month,
                "schedule_version_token": row.schedule_version_token,
                "opening_liability_reporting_currency": row.opening_liability_reporting_currency,
                "interest_expense_reporting_currency": row.interest_expense_reporting_currency,
                "payment_amount_reporting_currency": row.payment_amount_reporting_currency,
                "closing_liability_reporting_currency": row.closing_liability_reporting_currency,
                "fx_rate_used": row.fx_rate_used,
                "source_lease_reference": row.source_lease_reference,
                "parent_reference_id": row.parent_reference_id,
                "source_reference_id": row.source_reference_id,
                "correlation_id": correlation_id,
            },
            audit=AuditEvent(
                tenant_id=tenant_id,
                user_id=user_id,
                action="lease.liability_schedule.created",
                resource_type="lease_liability_schedule",
                new_value={
                    "run_id": str(run_id),
                    "lease_id": str(row.lease_id),
                    "schedule_date": row.schedule_date.isoformat(),
                    "schedule_version_token": row.schedule_version_token,
                    "correlation_id": correlation_id,
                },
            ),
        )
        inserted += 1

    remeasurement = await apply_lease_modifications(
        session,
        tenant_id=tenant_id,
        user_id=user_id,
        run_id=run_id,
        correlation_id=correlation_id,
        leases=payload.leases,
        registered_leases=leases,
        root_schedule_version_tokens=generated.root_schedule_version_tokens,
        reporting_currency=payload.reporting_currency,
        rate_mode=payload.rate_mode.value,
    )

    regenerated_inserted = 0
    for lease_id, modifications in remeasurement.modifications_by_lease.items():
        for modification in modifications:
            prior_rows = (
                await session.execute(
                    select(LeaseLiabilitySchedule)
                    .where(
                        LeaseLiabilitySchedule.tenant_id == tenant_id,
                        LeaseLiabilitySchedule.run_id == run_id,
                        LeaseLiabilitySchedule.lease_id == lease_id,
                        LeaseLiabilitySchedule.schedule_version_token == modification.prior_schedule_version_token,
                    )
                    .order_by(
                        LeaseLiabilitySchedule.schedule_date,
                        LeaseLiabilitySchedule.period_seq,
                        LeaseLiabilitySchedule.id,
                    )
                )
            ).scalars().all()
            if not prior_rows:
                continue
            historic = [row for row in prior_rows if row.schedule_date < modification.effective_date]
            forward = [row for row in prior_rows if row.schedule_date >= modification.effective_date]
            if not forward:
                continue

            running_opening = (
                historic[-1].closing_liability_reporting_currency
                if historic
                else forward[0].opening_liability_reporting_currency
            )
            period_seq = max((row.period_seq for row in historic), default=0)
            delta = modification.remeasurement_delta_reporting_currency
            for index, source_row in enumerate(forward):
                period_seq += 1
                opening = running_opening
                interest = source_row.interest_expense_reporting_currency
                payment = source_row.payment_amount_reporting_currency
                if index == 0 and delta != Decimal("0.000000"):
                    opening = Decimal(f"{(opening + delta):.6f}")
                closing = Decimal(f"{(opening + interest - payment):.6f}")

                existing_regenerated = await session.execute(
                    select(LeaseLiabilitySchedule).where(
                        LeaseLiabilitySchedule.tenant_id == tenant_id,
                        LeaseLiabilitySchedule.run_id == run_id,
                        LeaseLiabilitySchedule.lease_id == lease_id,
                        LeaseLiabilitySchedule.schedule_date == source_row.schedule_date,
                        LeaseLiabilitySchedule.schedule_version_token == modification.new_schedule_version_token,
                        LeaseLiabilitySchedule.period_seq == period_seq,
                    )
                )
                if existing_regenerated.scalar_one_or_none() is not None:
                    running_opening = closing
                    continue

                await AuditWriter.insert_financial_record(
                    session,
                    model_class=LeaseLiabilitySchedule,
                    tenant_id=tenant_id,
                    record_data={
                        "run_id": str(run_id),
                        "lease_id": str(lease_id),
                        "period_seq": period_seq,
                        "schedule_date": source_row.schedule_date.isoformat(),
                        "schedule_version_token": modification.new_schedule_version_token,
                    },
                    values={
                        "run_id": run_id,
                        "lease_id": lease_id,
                        "payment_id": source_row.payment_id,
                        "period_seq": period_seq,
                        "schedule_date": source_row.schedule_date,
                        "period_year": source_row.period_year,
                        "period_month": source_row.period_month,
                        "schedule_version_token": modification.new_schedule_version_token,
                        "opening_liability_reporting_currency": opening,
                        "interest_expense_reporting_currency": interest,
                        "payment_amount_reporting_currency": payment,
                        "closing_liability_reporting_currency": closing,
                        "fx_rate_used": source_row.fx_rate_used,
                        "source_lease_reference": source_row.source_lease_reference,
                        "parent_reference_id": source_row.parent_reference_id,
                        "source_reference_id": source_row.source_reference_id,
                        "correlation_id": correlation_id,
                    },
                    audit=AuditEvent(
                        tenant_id=tenant_id,
                        user_id=user_id,
                        action="lease.liability_schedule.regenerated",
                        resource_type="lease_liability_schedule",
                        new_value={
                            "run_id": str(run_id),
                            "lease_id": str(lease_id),
                            "schedule_date": source_row.schedule_date.isoformat(),
                            "schedule_version_token": modification.new_schedule_version_token,
                            "correlation_id": correlation_id,
                        },
                    ),
                )
                regenerated_inserted += 1
                running_opening = closing

    return {
        "liability_count": inserted + regenerated_inserted,
        "modification_count": remeasurement.modification_count,
    }


async def generate_rou_schedule_for_run(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
    user_id: UUID,
    correlation_id: str,
) -> dict[str, int]:
    del user_id
    run = await _get_run_or_raise(session, tenant_id=tenant_id, run_id=run_id)
    payload = _parse_request(run.configuration_json)
    leases = await register_leases(
        session,
        tenant_id=tenant_id,
        user_id=run.initiated_by,
        correlation_id=correlation_id,
        leases=payload.leases,
    )

    lease_ids = [lease.lease_id for lease in leases]
    effective_tokens: dict[UUID, str] = {}
    for lease_id in sorted(lease_ids, key=str):
        root_token = await _resolve_root_version_token(
            session,
            tenant_id=tenant_id,
            run_id=run_id,
            lease_id=lease_id,
        )
        if root_token is None:
            continue
        effective_tokens[lease_id] = await _resolve_effective_version_token(
            session,
            tenant_id=tenant_id,
            run_id=run_id,
            lease_id=lease_id,
            root_schedule_version_token=root_token,
        )

    liability_rows: list[LeaseLiabilitySchedule] = []
    for lease_id, token in effective_tokens.items():
        liability_rows.extend(
            (
                await session.execute(
                    select(LeaseLiabilitySchedule)
                    .where(
                        LeaseLiabilitySchedule.tenant_id == tenant_id,
                        LeaseLiabilitySchedule.run_id == run_id,
                        LeaseLiabilitySchedule.lease_id == lease_id,
                        LeaseLiabilitySchedule.schedule_version_token == token,
                    )
                    .order_by(
                        LeaseLiabilitySchedule.lease_id,
                        LeaseLiabilitySchedule.schedule_date,
                        LeaseLiabilitySchedule.period_seq,
                        LeaseLiabilitySchedule.id,
                    )
                )
            ).scalars().all()
        )
    if not liability_rows:
        raise AccountingValidationError(
            error_code=INVALID_EVENT_SEQUENCE,
            message="Cannot generate ROU schedule before liability schedule",
        )

    lease_id_by_number = {lease.lease_number: lease.lease_id for lease in leases}
    impairment_lookup: dict[UUID, dict[Any, Decimal]] = {}
    for lease in payload.leases:
        lease_id = lease_id_by_number[lease.lease_number]
        impairment_lookup[lease_id] = {
            impairment.schedule_date: impairment.impairment_amount_reporting_currency
            for impairment in lease.impairments
        }

    generated_rows = generate_rou_schedule_rows(
        leases=leases,
        liability_rows=liability_rows,
        impairments_by_lease=impairment_lookup,
    )

    inserted = 0
    for row in generated_rows:
        existing = await session.execute(
            select(LeaseRouSchedule).where(
                LeaseRouSchedule.tenant_id == tenant_id,
                LeaseRouSchedule.run_id == run_id,
                LeaseRouSchedule.lease_id == row.lease_id,
                LeaseRouSchedule.schedule_date == row.schedule_date,
                LeaseRouSchedule.schedule_version_token == row.schedule_version_token,
                LeaseRouSchedule.period_seq == row.period_seq,
            )
        )
        if existing.scalar_one_or_none() is not None:
            continue

        await AuditWriter.insert_financial_record(
            session,
            model_class=LeaseRouSchedule,
            tenant_id=tenant_id,
            record_data={
                "run_id": str(run_id),
                "lease_id": str(row.lease_id),
                "period_seq": row.period_seq,
                "schedule_date": row.schedule_date.isoformat(),
                "schedule_version_token": row.schedule_version_token,
            },
            values={
                "run_id": run_id,
                "lease_id": row.lease_id,
                "period_seq": row.period_seq,
                "schedule_date": row.schedule_date,
                "period_year": row.period_year,
                "period_month": row.period_month,
                "schedule_version_token": row.schedule_version_token,
                "opening_rou_reporting_currency": row.opening_rou_reporting_currency,
                "amortization_expense_reporting_currency": row.amortization_expense_reporting_currency,
                "impairment_amount_reporting_currency": row.impairment_amount_reporting_currency,
                "closing_rou_reporting_currency": row.closing_rou_reporting_currency,
                "fx_rate_used": row.fx_rate_used,
                "source_lease_reference": row.source_lease_reference,
                "parent_reference_id": row.parent_reference_id,
                "source_reference_id": row.source_reference_id,
                "correlation_id": correlation_id,
            },
            audit=AuditEvent(
                tenant_id=tenant_id,
                user_id=run.initiated_by,
                action="lease.rou_schedule.created",
                resource_type="lease_rou_schedule",
                new_value={
                    "run_id": str(run_id),
                    "lease_id": str(row.lease_id),
                    "schedule_date": row.schedule_date.isoformat(),
                    "schedule_version_token": row.schedule_version_token,
                    "correlation_id": correlation_id,
                },
            ),
        )
        inserted += 1
    return {"rou_count": inserted}


async def _insert_journal_row(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: UUID,
    run_id: UUID,
    lease_id: UUID,
    liability_schedule_id: UUID | None,
    rou_schedule_id: UUID | None,
    sequence: int,
    entry_date: Any,
    debit_account: str,
    credit_account: str,
    amount_reporting_currency: Decimal,
    source_lease_reference: str,
    parent_reference_id: UUID,
    source_reference_id: UUID,
    correlation_id: str,
) -> bool:
    if amount_reporting_currency <= Decimal("0.000000"):
        return False

    existing = await session.execute(
        select(LeaseJournalEntry).where(
            LeaseJournalEntry.tenant_id == tenant_id,
            LeaseJournalEntry.run_id == run_id,
            LeaseJournalEntry.liability_schedule_id == liability_schedule_id,
            LeaseJournalEntry.rou_schedule_id == rou_schedule_id,
            LeaseJournalEntry.debit_account == debit_account,
            LeaseJournalEntry.credit_account == credit_account,
        )
    )
    if existing.scalar_one_or_none() is not None:
        return False

    await AuditWriter.insert_financial_record(
        session,
        model_class=LeaseJournalEntry,
        tenant_id=tenant_id,
        record_data={
            "run_id": str(run_id),
            "lease_id": str(lease_id),
            "journal_reference": build_journal_reference(
                engine_namespace="LSE",
                run_id=run_id,
                sequence=sequence,
            ),
        },
        values={
            "run_id": run_id,
            "lease_id": lease_id,
            "liability_schedule_id": liability_schedule_id,
            "rou_schedule_id": rou_schedule_id,
            "journal_reference": build_journal_reference(
                engine_namespace="LSE",
                run_id=run_id,
                sequence=sequence,
            ),
            "entry_date": entry_date,
            "debit_account": debit_account,
            "credit_account": credit_account,
            "amount_reporting_currency": amount_reporting_currency,
            "source_lease_reference": source_lease_reference,
            "parent_reference_id": parent_reference_id,
            "source_reference_id": source_reference_id,
            "correlation_id": correlation_id,
        },
        audit=AuditEvent(
            tenant_id=tenant_id,
            user_id=user_id,
            action="lease.journal.preview.created",
            resource_type="lease_journal_entry",
            new_value={
                "run_id": str(run_id),
                "lease_id": str(lease_id),
                "journal_sequence": sequence,
                "correlation_id": correlation_id,
            },
        ),
    )
    return True


async def build_journal_preview_for_run(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
    user_id: UUID,
    correlation_id: str,
) -> dict[str, int]:
    lease_ids = (
        await session.execute(
            select(LeaseLiabilitySchedule.lease_id)
            .where(
                LeaseLiabilitySchedule.tenant_id == tenant_id,
                LeaseLiabilitySchedule.run_id == run_id,
            )
            .distinct()
            .order_by(LeaseLiabilitySchedule.lease_id)
        )
    ).scalars().all()

    effective_tokens: dict[UUID, str] = {}
    for lease_id in lease_ids:
        root_token = await _resolve_root_version_token(
            session,
            tenant_id=tenant_id,
            run_id=run_id,
            lease_id=lease_id,
        )
        if root_token is None:
            continue
        effective_tokens[lease_id] = await _resolve_effective_version_token(
            session,
            tenant_id=tenant_id,
            run_id=run_id,
            lease_id=lease_id,
            root_schedule_version_token=root_token,
        )

    liability_rows: list[LeaseLiabilitySchedule] = []
    rou_rows: list[LeaseRouSchedule] = []
    for lease_id, token in effective_tokens.items():
        liability_rows.extend(
            (
                await session.execute(
                    select(LeaseLiabilitySchedule)
                    .where(
                        LeaseLiabilitySchedule.tenant_id == tenant_id,
                        LeaseLiabilitySchedule.run_id == run_id,
                        LeaseLiabilitySchedule.lease_id == lease_id,
                        LeaseLiabilitySchedule.schedule_version_token == token,
                    )
                    .order_by(
                        LeaseLiabilitySchedule.schedule_date,
                        LeaseLiabilitySchedule.lease_id,
                        LeaseLiabilitySchedule.period_seq,
                        LeaseLiabilitySchedule.id,
                    )
                )
            ).scalars().all()
        )
        rou_rows.extend(
            (
                await session.execute(
                    select(LeaseRouSchedule)
                    .where(
                        LeaseRouSchedule.tenant_id == tenant_id,
                        LeaseRouSchedule.run_id == run_id,
                        LeaseRouSchedule.lease_id == lease_id,
                        LeaseRouSchedule.schedule_version_token == token,
                    )
                    .order_by(
                        LeaseRouSchedule.schedule_date,
                        LeaseRouSchedule.lease_id,
                        LeaseRouSchedule.period_seq,
                        LeaseRouSchedule.id,
                    )
                )
            ).scalars().all()
        )

    sequence = 1
    inserted = 0

    for row in liability_rows:
        if await _insert_journal_row(
            session,
            tenant_id=tenant_id,
            user_id=user_id,
            run_id=run_id,
            lease_id=row.lease_id,
            liability_schedule_id=row.id,
            rou_schedule_id=None,
            sequence=sequence,
            entry_date=row.schedule_date,
            debit_account="Lease Interest Expense",
            credit_account="Lease Liability",
            amount_reporting_currency=row.interest_expense_reporting_currency,
            source_lease_reference=row.source_lease_reference,
            parent_reference_id=row.id,
            source_reference_id=row.source_reference_id or row.lease_id,
            correlation_id=correlation_id,
        ):
            inserted += 1
            sequence += 1

        if await _insert_journal_row(
            session,
            tenant_id=tenant_id,
            user_id=user_id,
            run_id=run_id,
            lease_id=row.lease_id,
            liability_schedule_id=row.id,
            rou_schedule_id=None,
            sequence=sequence,
            entry_date=row.schedule_date,
            debit_account="Lease Liability",
            credit_account="Cash",
            amount_reporting_currency=row.payment_amount_reporting_currency,
            source_lease_reference=row.source_lease_reference,
            parent_reference_id=row.id,
            source_reference_id=row.source_reference_id or row.lease_id,
            correlation_id=correlation_id,
        ):
            inserted += 1
            sequence += 1

    for row in rou_rows:
        amount = row.amortization_expense_reporting_currency + row.impairment_amount_reporting_currency
        if await _insert_journal_row(
            session,
            tenant_id=tenant_id,
            user_id=user_id,
            run_id=run_id,
            lease_id=row.lease_id,
            liability_schedule_id=None,
            rou_schedule_id=row.id,
            sequence=sequence,
            entry_date=row.schedule_date,
            debit_account="Lease Expense",
            credit_account="ROU Asset",
            amount_reporting_currency=amount,
            source_lease_reference=row.source_lease_reference,
            parent_reference_id=row.id,
            source_reference_id=row.source_reference_id or row.lease_id,
            correlation_id=correlation_id,
        ):
            inserted += 1
            sequence += 1

    return {"journal_count": inserted}


async def validate_lineage_for_run(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
) -> LineageValidationResult:
    result = await validate_lease_lineage(
        session,
        tenant_id=tenant_id,
        run_id=run_id,
    )
    if not result.is_complete:
        raise AccountingValidationError(error_code=LINEAGE_INCOMPLETE)
    return result


async def finalize_run(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
    user_id: UUID,
    correlation_id: str,
    event_type: str,
    metadata_json: dict[str, Any] | None,
) -> LeaseRunEvent:
    if event_type not in TERMINAL_EVENT_TYPES:
        raise AccountingValidationError(
            error_code=INVALID_EVENT_SEQUENCE,
            message="Invalid terminal run event type",
        )

    if event_type in {RUN_EVENT_COMPLETED, RUN_EVENT_COMPLETED_WITH_WARNINGS}:
        await validate_lineage_before_finalize(
            session,
            event_model=LeaseRunEvent,
            tenant_id=tenant_id,
            run_id=run_id,
            user_id=user_id,
            correlation_id=correlation_id,
            audit_namespace=_AUDIT_NAMESPACE,
            lineage_validator=lambda: validate_lease_lineage(
                session,
                tenant_id=tenant_id,
                run_id=run_id,
            ),
        )

    existing_terminal = await session.execute(
        select(LeaseRunEvent)
        .where(
            LeaseRunEvent.tenant_id == tenant_id,
            LeaseRunEvent.run_id == run_id,
            LeaseRunEvent.event_type.in_(list(TERMINAL_EVENT_TYPES)),
        )
        .order_by(desc(LeaseRunEvent.event_seq))
        .limit(1)
    )
    terminal = existing_terminal.scalar_one_or_none()
    if terminal is not None:
        return terminal

    return await append_event(
        session,
        event_model=LeaseRunEvent,
        tenant_id=tenant_id,
        run_id=run_id,
        user_id=user_id,
        event_type=event_type,
        idempotency_key=f"terminal:{event_type}",
        metadata_json=metadata_json,
        correlation_id=correlation_id,
        audit_namespace=_AUDIT_NAMESPACE,
    )


async def get_run_status(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
) -> dict[str, Any]:
    latest = await derive_latest_status(
        session,
        run_model=LeaseRun,
        event_model=LeaseRunEvent,
        tenant_id=tenant_id,
        run_id=run_id,
    )
    return {
        "run_id": str(latest.run_id),
        "status": latest.status,
        "event_seq": latest.event_seq,
        "event_time": latest.event_time,
        "metadata": latest.metadata,
    }


async def get_results(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
) -> dict[str, Any]:
    run = await _get_run_or_raise(session, tenant_id=tenant_id, run_id=run_id)
    reporting_currency = str(run.configuration_json.get("reporting_currency", ""))

    lease_ids = (
        await session.execute(
            select(LeaseLiabilitySchedule.lease_id)
            .where(
                LeaseLiabilitySchedule.tenant_id == tenant_id,
                LeaseLiabilitySchedule.run_id == run_id,
            )
            .distinct()
            .order_by(LeaseLiabilitySchedule.lease_id)
        )
    ).scalars().all()

    effective_tokens: dict[UUID, str] = {}
    for lease_id in lease_ids:
        root_token = await _resolve_root_version_token(
            session,
            tenant_id=tenant_id,
            run_id=run_id,
            lease_id=lease_id,
        )
        if root_token is None:
            continue
        effective_tokens[lease_id] = await _resolve_effective_version_token(
            session,
            tenant_id=tenant_id,
            run_id=run_id,
            lease_id=lease_id,
            root_schedule_version_token=root_token,
        )

    liability_rows: list[LeaseLiabilitySchedule] = []
    rou_rows: list[LeaseRouSchedule] = []
    for lease_id, token in effective_tokens.items():
        liability_rows.extend(
            (
                await session.execute(
                    select(LeaseLiabilitySchedule)
                    .where(
                        LeaseLiabilitySchedule.tenant_id == tenant_id,
                        LeaseLiabilitySchedule.run_id == run_id,
                        LeaseLiabilitySchedule.lease_id == lease_id,
                        LeaseLiabilitySchedule.schedule_version_token == token,
                    )
                    .order_by(
                        LeaseLiabilitySchedule.schedule_date,
                        LeaseLiabilitySchedule.lease_id,
                        LeaseLiabilitySchedule.period_seq,
                        LeaseLiabilitySchedule.id,
                    )
                )
            ).scalars().all()
        )
        rou_rows.extend(
            (
                await session.execute(
                    select(LeaseRouSchedule)
                    .where(
                        LeaseRouSchedule.tenant_id == tenant_id,
                        LeaseRouSchedule.run_id == run_id,
                        LeaseRouSchedule.lease_id == lease_id,
                        LeaseRouSchedule.schedule_version_token == token,
                    )
                    .order_by(
                        LeaseRouSchedule.schedule_date,
                        LeaseRouSchedule.lease_id,
                        LeaseRouSchedule.period_seq,
                        LeaseRouSchedule.id,
                    )
                )
            ).scalars().all()
        )

    return {
        "run_id": str(run_id),
        "reporting_currency": reporting_currency,
        "liability_rows": [
            {
                "line_id": str(row.id),
                "lease_id": str(row.lease_id),
                "period_seq": row.period_seq,
                "schedule_date": row.schedule_date,
                "schedule_version_token": row.schedule_version_token,
                "opening_liability_reporting_currency": f"{row.opening_liability_reporting_currency:.6f}",
                "interest_expense_reporting_currency": f"{row.interest_expense_reporting_currency:.6f}",
                "payment_amount_reporting_currency": f"{row.payment_amount_reporting_currency:.6f}",
                "closing_liability_reporting_currency": f"{row.closing_liability_reporting_currency:.6f}",
            }
            for row in liability_rows
        ],
        "rou_rows": [
            {
                "line_id": str(row.id),
                "lease_id": str(row.lease_id),
                "period_seq": row.period_seq,
                "schedule_date": row.schedule_date,
                "schedule_version_token": row.schedule_version_token,
                "opening_rou_reporting_currency": f"{row.opening_rou_reporting_currency:.6f}",
                "amortization_expense_reporting_currency": f"{row.amortization_expense_reporting_currency:.6f}",
                "impairment_amount_reporting_currency": f"{row.impairment_amount_reporting_currency:.6f}",
                "closing_rou_reporting_currency": f"{row.closing_rou_reporting_currency:.6f}",
            }
            for row in rou_rows
        ],
        "liability_count": len(liability_rows),
        "rou_count": len(rou_rows),
        "total_interest_reporting_currency": f"{sum((row.interest_expense_reporting_currency for row in liability_rows), start=Decimal('0.000000')):.6f}",
        "total_amortization_reporting_currency": f"{sum((row.amortization_expense_reporting_currency for row in rou_rows), start=Decimal('0.000000')):.6f}",
    }


async def get_lease_drilldown(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
    lease_id: UUID,
) -> dict[str, Any]:
    return await get_lease_drill(
        session,
        tenant_id=tenant_id,
        run_id=run_id,
        lease_id=lease_id,
    )


async def get_payment_drilldown(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
    payment_id: UUID,
) -> dict[str, Any]:
    return await get_payment_drill(
        session,
        tenant_id=tenant_id,
        run_id=run_id,
        payment_id=payment_id,
    )


async def get_liability_drilldown(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
    line_id: UUID,
) -> dict[str, Any]:
    return await get_liability_drill(
        session,
        tenant_id=tenant_id,
        run_id=run_id,
        line_id=line_id,
    )


async def get_rou_drilldown(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
    line_id: UUID,
) -> dict[str, Any]:
    return await get_rou_drill(
        session,
        tenant_id=tenant_id,
        run_id=run_id,
        line_id=line_id,
    )


async def get_journal_drilldown(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
    journal_id: UUID,
) -> dict[str, Any]:
    return await get_journal_drill(
        session,
        tenant_id=tenant_id,
        run_id=run_id,
        journal_id=journal_id,
    )


async def get_drill(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
    record_id: UUID,
) -> dict[str, Any]:
    return await get_liability_drilldown(
        session,
        tenant_id=tenant_id,
        run_id=run_id,
        line_id=record_id,
    )


def register_workflow() -> type[Any]:
    from financeops.temporal.lease_workflows import LeaseAccountingWorkflow

    return LeaseAccountingWorkflow


class LeaseFacade:
    """Compatibility facade exposing lease service entrypoints."""

    create_run = staticmethod(create_run)
    mark_run_running = staticmethod(mark_run_running)
    load_leases_and_payments_for_run = staticmethod(load_leases_and_payments_for_run)
    build_payment_timeline_for_run = staticmethod(build_payment_timeline_for_run)
    calculate_present_value_for_run = staticmethod(calculate_present_value_for_run)
    generate_liability_schedule_for_run = staticmethod(generate_liability_schedule_for_run)
    generate_rou_schedule_for_run = staticmethod(generate_rou_schedule_for_run)
    build_journal_preview_for_run = staticmethod(build_journal_preview_for_run)
    validate_lineage_for_run = staticmethod(validate_lineage_for_run)
    finalize_run = staticmethod(finalize_run)
    get_run_status = staticmethod(get_run_status)
    get_results = staticmethod(get_results)

