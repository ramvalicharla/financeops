from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import NotFoundError, ValidationError
from financeops.db.models.revenue import (
    RevenueAdjustment,
    RevenueJournalEntry,
    RevenuePerformanceObligation,
    RevenueRun,
    RevenueRunEvent,
    RevenueSchedule,
)
from financeops.schemas.revenue import RevenueRunRequest
from financeops.services.accounting_common.accounting_errors import AccountingValidationError
from financeops.services.accounting_common.error_codes import (
    INVALID_EVENT_SEQUENCE,
    LINEAGE_INCOMPLETE,
)
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
from financeops.services.revenue.allocation_engine import allocate_contract_values
from financeops.services.revenue.contract_registry import register_contracts
from financeops.services.revenue.drilldown_service import (
    get_contract_drill,
    get_journal_drill,
    get_obligation_drill,
    get_schedule_drill,
)
from financeops.services.revenue.journal_preview import build_revenue_journal_preview
from financeops.services.revenue.lineage_validation import validate_revenue_lineage
from financeops.services.revenue.obligation_tracker import register_obligations_and_line_items
from financeops.services.revenue.remeasurement import apply_contract_modifications
from financeops.services.revenue.schedule_generator import generate_schedule_rows

_AUDIT_NAMESPACE = "revenue"


async def _get_run_or_raise(session: AsyncSession, *, tenant_id: UUID, run_id: UUID) -> RevenueRun:
    result = await session.execute(
        select(RevenueRun).where(
            RevenueRun.tenant_id == tenant_id,
            RevenueRun.id == run_id,
        )
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise NotFoundError("Revenue run not found")
    return run


def _parse_request(configuration_json: dict[str, Any]) -> RevenueRunRequest:
    return RevenueRunRequest.model_validate(configuration_json)


async def _resolve_root_version_token(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
    contract_id: UUID,
) -> str | None:
    first_adjustment = (
        await session.execute(
            select(RevenueAdjustment)
            .where(
                RevenueAdjustment.tenant_id == tenant_id,
                RevenueAdjustment.run_id == run_id,
                RevenueAdjustment.contract_id == contract_id,
            )
            .order_by(
                RevenueAdjustment.effective_date,
                RevenueAdjustment.created_at,
                RevenueAdjustment.id,
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if first_adjustment is not None:
        return first_adjustment.prior_schedule_version_token

    first_schedule = await session.execute(
        select(RevenueSchedule.schedule_version_token)
        .where(
            RevenueSchedule.tenant_id == tenant_id,
            RevenueSchedule.run_id == run_id,
            RevenueSchedule.contract_id == contract_id,
        )
        .order_by(
            RevenueSchedule.created_at,
            RevenueSchedule.period_seq,
            RevenueSchedule.id,
        )
        .limit(1)
    )
    return first_schedule.scalar_one_or_none()


async def _resolve_effective_version_token(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
    contract_id: UUID,
    root_schedule_version_token: str,
) -> str:
    latest_adjustment = (
        await session.execute(
            select(RevenueAdjustment)
            .where(
                RevenueAdjustment.tenant_id == tenant_id,
                RevenueAdjustment.run_id == run_id,
                RevenueAdjustment.contract_id == contract_id,
            )
            .order_by(
                desc(RevenueAdjustment.effective_date),
                desc(RevenueAdjustment.created_at),
                desc(RevenueAdjustment.id),
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if latest_adjustment is None:
        return root_schedule_version_token
    return latest_adjustment.new_schedule_version_token


async def create_run(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    initiated_by: UUID,
    request_payload: dict[str, Any],
    correlation_id: str,
) -> dict[str, Any]:
    payload = RevenueRunRequest.model_validate(request_payload)
    signature = build_request_signature(payload.model_dump(mode="json"))
    workflow_id = f"revenue-{signature[:24]}"

    result = await create_run_header(
        session,
        run_model=RevenueRun,
        event_model=RevenueRunEvent,
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
) -> RevenueRunEvent:
    return await append_event(
        session,
        event_model=RevenueRunEvent,
        tenant_id=tenant_id,
        run_id=run_id,
        user_id=user_id,
        event_type=RUN_EVENT_RUNNING,
        idempotency_key="stage-running",
        metadata_json=None,
        correlation_id=correlation_id,
        audit_namespace=_AUDIT_NAMESPACE,
    )


async def load_contracts_and_obligations_for_run(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
    user_id: UUID,
    correlation_id: str,
) -> dict[str, int]:
    run = await _get_run_or_raise(session, tenant_id=tenant_id, run_id=run_id)
    payload = _parse_request(run.configuration_json)

    contracts = await register_contracts(
        session,
        tenant_id=tenant_id,
        user_id=user_id,
        correlation_id=correlation_id,
        contracts=payload.contracts,
    )
    obligation_set = await register_obligations_and_line_items(
        session,
        tenant_id=tenant_id,
        user_id=user_id,
        correlation_id=correlation_id,
        contracts=payload.contracts,
        registered_contracts=contracts,
    )
    return {
        "contract_count": len(contracts),
        "obligation_count": len(obligation_set.obligations),
        "line_item_count": len(obligation_set.line_items),
    }


async def allocate_contract_value_for_run(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
    user_id: UUID,
    correlation_id: str,
) -> dict[str, str]:
    run = await _get_run_or_raise(session, tenant_id=tenant_id, run_id=run_id)
    payload = _parse_request(run.configuration_json)

    contracts = await register_contracts(
        session,
        tenant_id=tenant_id,
        user_id=user_id,
        correlation_id=correlation_id,
        contracts=payload.contracts,
    )
    obligation_set = await register_obligations_and_line_items(
        session,
        tenant_id=tenant_id,
        user_id=user_id,
        correlation_id=correlation_id,
        contracts=payload.contracts,
        registered_contracts=contracts,
    )
    allocations = allocate_contract_values(
        contracts=contracts,
        obligations=obligation_set.obligations,
    )
    total_allocated = sum(
        (item.allocated_amount_contract_currency for item in allocations),
        start=Decimal("0.000000"),
    )
    return {
        "allocation_count": str(len(allocations)),
        "total_allocated_contract_currency": str(total_allocated),
    }


async def generate_revenue_schedule_for_run(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
    user_id: UUID,
    correlation_id: str,
) -> dict[str, int]:
    run = await _get_run_or_raise(session, tenant_id=tenant_id, run_id=run_id)
    payload = _parse_request(run.configuration_json)

    contracts = await register_contracts(
        session,
        tenant_id=tenant_id,
        user_id=user_id,
        correlation_id=correlation_id,
        contracts=payload.contracts,
    )
    obligation_set = await register_obligations_and_line_items(
        session,
        tenant_id=tenant_id,
        user_id=user_id,
        correlation_id=correlation_id,
        contracts=payload.contracts,
        registered_contracts=contracts,
    )
    allocations = allocate_contract_values(
        contracts=contracts,
        obligations=obligation_set.obligations,
    )
    generated = await generate_schedule_rows(
        session,
        tenant_id=tenant_id,
        contracts=contracts,
        line_items=obligation_set.line_items,
        allocations=allocations,
        reporting_currency=payload.reporting_currency,
        rate_mode=payload.rate_mode,
    )

    inserted = 0
    for row in generated.rows:
        existing_schedule = await session.execute(
            select(RevenueSchedule).where(
                RevenueSchedule.tenant_id == tenant_id,
                RevenueSchedule.run_id == run_id,
                RevenueSchedule.contract_id == row.contract_id,
                RevenueSchedule.recognition_date == row.recognition_date,
                RevenueSchedule.schedule_version_token == row.schedule_version_token,
                RevenueSchedule.period_seq == row.period_seq,
            )
        )
        if existing_schedule.scalar_one_or_none() is not None:
            continue

        await AuditWriter.insert_financial_record(
            session,
            model_class=RevenueSchedule,
            tenant_id=tenant_id,
            record_data={
                "run_id": str(run_id),
                "contract_id": str(row.contract_id),
                "obligation_id": str(row.obligation_id),
                "contract_line_item_id": str(row.contract_line_item_id),
                "period_seq": row.period_seq,
                "recognition_date": row.recognition_date.isoformat(),
                "schedule_version_token": row.schedule_version_token,
            },
            values={
                "run_id": run_id,
                "contract_id": row.contract_id,
                "obligation_id": row.obligation_id,
                "contract_line_item_id": row.contract_line_item_id,
                "period_seq": row.period_seq,
                "recognition_date": row.recognition_date,
                "recognition_period_year": row.recognition_period_year,
                "recognition_period_month": row.recognition_period_month,
                "schedule_version_token": row.schedule_version_token,
                "recognition_method": row.recognition_method,
                "base_amount_contract_currency": row.base_amount_contract_currency,
                "fx_rate_used": row.fx_rate_used,
                "recognized_amount_reporting_currency": row.recognized_amount_reporting_currency,
                "cumulative_recognized_reporting_currency": row.cumulative_recognized_reporting_currency,
                "schedule_status": row.schedule_status,
                "source_contract_reference": row.source_contract_reference,
                "parent_reference_id": row.parent_reference_id,
                "source_reference_id": row.source_reference_id,
                "correlation_id": correlation_id,
            },
            audit=AuditEvent(
                tenant_id=tenant_id,
                user_id=user_id,
                action="revenue.schedule.created",
                resource_type="revenue_schedule",
                new_value={
                    "run_id": str(run_id),
                    "contract_line_item_id": str(row.contract_line_item_id),
                    "recognition_date": row.recognition_date.isoformat(),
                    "schedule_version_token": row.schedule_version_token,
                    "correlation_id": correlation_id,
                },
            ),
        )
        inserted += 1

    remeasurement = await apply_contract_modifications(
        session,
        tenant_id=tenant_id,
        user_id=user_id,
        run_id=run_id,
        correlation_id=correlation_id,
        contracts=payload.contracts,
        registered_contracts=contracts,
        root_schedule_version_tokens=generated.root_schedule_version_tokens,
        reporting_currency=payload.reporting_currency,
        rate_mode=payload.rate_mode.value,
    )

    regenerated_inserted = 0
    for contract_id, adjustments in remeasurement.adjustments_by_contract.items():
        for adjustment in adjustments:
            prior_rows = (
                await session.execute(
                    select(RevenueSchedule)
                    .where(
                        RevenueSchedule.tenant_id == tenant_id,
                        RevenueSchedule.run_id == run_id,
                        RevenueSchedule.contract_id == contract_id,
                        RevenueSchedule.schedule_version_token == adjustment.prior_schedule_version_token,
                    )
                    .order_by(
                        RevenueSchedule.recognition_date,
                        RevenueSchedule.period_seq,
                        RevenueSchedule.id,
                    )
                )
            ).scalars().all()
            if not prior_rows:
                continue
            historic = [row for row in prior_rows if row.recognition_date < adjustment.effective_date]
            forward = [row for row in prior_rows if row.recognition_date >= adjustment.effective_date]
            if not forward:
                continue

            running = (
                historic[-1].cumulative_recognized_reporting_currency
                if historic
                else Decimal("0.000000")
            )
            period_seq = max((row.period_seq for row in historic), default=0)
            for index, source_row in enumerate(forward):
                recognized = source_row.recognized_amount_reporting_currency
                if index == 0 and adjustment.catch_up_amount_reporting_currency != Decimal("0.000000"):
                    recognized = recognized + adjustment.catch_up_amount_reporting_currency
                recognized = Decimal(f"{recognized:.6f}")
                running = Decimal(f"{(running + recognized):.6f}")
                period_seq += 1

                existing_regenerated = await session.execute(
                    select(RevenueSchedule).where(
                        RevenueSchedule.tenant_id == tenant_id,
                        RevenueSchedule.run_id == run_id,
                        RevenueSchedule.contract_id == contract_id,
                        RevenueSchedule.recognition_date == source_row.recognition_date,
                        RevenueSchedule.schedule_version_token == adjustment.new_schedule_version_token,
                        RevenueSchedule.period_seq == period_seq,
                    )
                )
                if existing_regenerated.scalar_one_or_none() is not None:
                    continue

                await AuditWriter.insert_financial_record(
                    session,
                    model_class=RevenueSchedule,
                    tenant_id=tenant_id,
                    record_data={
                        "run_id": str(run_id),
                        "contract_id": str(source_row.contract_id),
                        "obligation_id": str(source_row.obligation_id),
                        "contract_line_item_id": str(source_row.contract_line_item_id),
                        "period_seq": period_seq,
                        "recognition_date": source_row.recognition_date.isoformat(),
                        "schedule_version_token": adjustment.new_schedule_version_token,
                    },
                    values={
                        "run_id": run_id,
                        "contract_id": source_row.contract_id,
                        "obligation_id": source_row.obligation_id,
                        "contract_line_item_id": source_row.contract_line_item_id,
                        "period_seq": period_seq,
                        "recognition_date": source_row.recognition_date,
                        "recognition_period_year": source_row.recognition_period_year,
                        "recognition_period_month": source_row.recognition_period_month,
                        "schedule_version_token": adjustment.new_schedule_version_token,
                        "recognition_method": source_row.recognition_method,
                        "base_amount_contract_currency": source_row.base_amount_contract_currency,
                        "fx_rate_used": source_row.fx_rate_used,
                        "recognized_amount_reporting_currency": recognized,
                        "cumulative_recognized_reporting_currency": running,
                        "schedule_status": "regenerated",
                        "source_contract_reference": source_row.source_contract_reference,
                        "parent_reference_id": source_row.parent_reference_id,
                        "source_reference_id": source_row.source_reference_id,
                        "correlation_id": correlation_id,
                    },
                    audit=AuditEvent(
                        tenant_id=tenant_id,
                        user_id=user_id,
                        action="revenue.schedule.regenerated",
                        resource_type="revenue_schedule",
                        new_value={
                            "run_id": str(run_id),
                            "contract_id": str(source_row.contract_id),
                            "recognition_date": source_row.recognition_date.isoformat(),
                            "schedule_version_token": adjustment.new_schedule_version_token,
                            "correlation_id": correlation_id,
                        },
                    ),
                )
                regenerated_inserted += 1

    return {
        "schedule_count": inserted + regenerated_inserted,
        "adjustment_count": remeasurement.adjustment_count,
    }


async def build_journal_preview_for_run(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
    user_id: UUID,
    correlation_id: str,
) -> dict[str, int]:
    contract_ids = (
        await session.execute(
            select(RevenueSchedule.contract_id)
            .where(
                RevenueSchedule.tenant_id == tenant_id,
                RevenueSchedule.run_id == run_id,
            )
            .distinct()
            .order_by(RevenueSchedule.contract_id)
        )
    ).scalars().all()

    effective_tokens: dict[UUID, str] = {}
    for contract_id in contract_ids:
        root_token = await _resolve_root_version_token(
            session,
            tenant_id=tenant_id,
            run_id=run_id,
            contract_id=contract_id,
        )
        if root_token is None:
            continue
        effective_tokens[contract_id] = await _resolve_effective_version_token(
            session,
            tenant_id=tenant_id,
            run_id=run_id,
            contract_id=contract_id,
            root_schedule_version_token=root_token,
        )

    schedules: list[RevenueSchedule] = []
    for contract_id, token in effective_tokens.items():
        schedules.extend(
            (
                await session.execute(
                    select(RevenueSchedule)
                    .where(
                        RevenueSchedule.tenant_id == tenant_id,
                        RevenueSchedule.run_id == run_id,
                        RevenueSchedule.contract_id == contract_id,
                        RevenueSchedule.schedule_version_token == token,
                    )
                    .order_by(
                        RevenueSchedule.recognition_date,
                        RevenueSchedule.contract_id,
                        RevenueSchedule.period_seq,
                        RevenueSchedule.id,
                    )
                )
            ).scalars().all()
        )
    schedules.sort(
        key=lambda row: (
            row.recognition_date,
            str(row.contract_id),
            row.period_seq,
            str(row.id),
        )
    )

    preview_rows = build_revenue_journal_preview(run_id=run_id, schedules=list(schedules))
    inserted = 0
    for row in preview_rows:
        existing = await session.execute(
            select(RevenueJournalEntry).where(
                RevenueJournalEntry.tenant_id == tenant_id,
                RevenueJournalEntry.run_id == run_id,
                RevenueJournalEntry.schedule_id == row.schedule_id,
            )
        )
        if existing.scalar_one_or_none() is not None:
            continue

        await AuditWriter.insert_financial_record(
            session,
            model_class=RevenueJournalEntry,
            tenant_id=tenant_id,
            record_data={
                "run_id": str(run_id),
                "schedule_id": str(row.schedule_id),
                "journal_reference": row.journal_reference,
            },
            values={
                "run_id": run_id,
                "contract_id": row.contract_id,
                "obligation_id": row.obligation_id,
                "schedule_id": row.schedule_id,
                "journal_reference": row.journal_reference,
                "entry_date": row.entry_date,
                "debit_account": row.debit_account,
                "credit_account": row.credit_account,
                "amount_reporting_currency": row.amount_reporting_currency,
                "source_contract_reference": row.source_contract_reference,
                "parent_reference_id": row.parent_reference_id,
                "source_reference_id": row.source_reference_id,
                "correlation_id": correlation_id,
            },
            audit=AuditEvent(
                tenant_id=tenant_id,
                user_id=user_id,
                action="revenue.journal.preview.created",
                resource_type="revenue_journal_entry",
                new_value={
                    "run_id": str(run_id),
                    "schedule_id": str(row.schedule_id),
                    "journal_reference": row.journal_reference,
                    "correlation_id": correlation_id,
                },
            ),
        )
        inserted += 1

    return {"journal_count": inserted}


async def validate_lineage_for_run(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
) -> LineageValidationResult:
    result = await validate_revenue_lineage(
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
) -> RevenueRunEvent:
    if event_type not in TERMINAL_EVENT_TYPES:
        raise AccountingValidationError(
            error_code=INVALID_EVENT_SEQUENCE,
            message="Invalid terminal run event type",
        )

    if event_type in {RUN_EVENT_COMPLETED, RUN_EVENT_COMPLETED_WITH_WARNINGS}:
        await validate_lineage_before_finalize(
            session,
            event_model=RevenueRunEvent,
            tenant_id=tenant_id,
            run_id=run_id,
            user_id=user_id,
            correlation_id=correlation_id,
            audit_namespace=_AUDIT_NAMESPACE,
            lineage_validator=lambda: validate_revenue_lineage(
                session,
                tenant_id=tenant_id,
                run_id=run_id,
            ),
        )

    existing_terminal = await session.execute(
        select(RevenueRunEvent)
        .where(
            RevenueRunEvent.tenant_id == tenant_id,
            RevenueRunEvent.run_id == run_id,
            RevenueRunEvent.event_type.in_(list(TERMINAL_EVENT_TYPES)),
        )
        .order_by(desc(RevenueRunEvent.event_seq))
        .limit(1)
    )
    terminal = existing_terminal.scalar_one_or_none()
    if terminal is not None:
        return terminal

    return await append_event(
        session,
        event_model=RevenueRunEvent,
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
        run_model=RevenueRun,
        event_model=RevenueRunEvent,
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

    contract_ids = (
        await session.execute(
            select(RevenueSchedule.contract_id)
            .where(
                RevenueSchedule.tenant_id == tenant_id,
                RevenueSchedule.run_id == run_id,
            )
            .distinct()
            .order_by(RevenueSchedule.contract_id)
        )
    ).scalars().all()

    effective_tokens: dict[UUID, str] = {}
    for contract_id in contract_ids:
        root_token = await _resolve_root_version_token(
            session,
            tenant_id=tenant_id,
            run_id=run_id,
            contract_id=contract_id,
        )
        if root_token is None:
            continue
        effective_tokens[contract_id] = await _resolve_effective_version_token(
            session,
            tenant_id=tenant_id,
            run_id=run_id,
            contract_id=contract_id,
            root_schedule_version_token=root_token,
        )

    rows: list[RevenueSchedule] = []
    for contract_id, token in effective_tokens.items():
        rows.extend(
            (
                await session.execute(
                    select(RevenueSchedule)
                    .where(
                        RevenueSchedule.tenant_id == tenant_id,
                        RevenueSchedule.run_id == run_id,
                        RevenueSchedule.contract_id == contract_id,
                        RevenueSchedule.schedule_version_token == token,
                    )
                    .order_by(
                        RevenueSchedule.recognition_date,
                        RevenueSchedule.contract_id,
                        RevenueSchedule.period_seq,
                        RevenueSchedule.id,
                    )
                )
            ).scalars().all()
        )
    rows.sort(key=lambda row: (row.recognition_date, str(row.contract_id), row.period_seq, str(row.id)))

    payload_rows = [
        {
            "schedule_id": str(row.id),
            "contract_id": str(row.contract_id),
            "obligation_id": str(row.obligation_id),
            "contract_line_item_id": str(row.contract_line_item_id),
            "period_seq": row.period_seq,
            "recognition_date": row.recognition_date,
            "schedule_version_token": row.schedule_version_token,
            "recognition_method": row.recognition_method,
            "recognized_amount_reporting_currency": str(row.recognized_amount_reporting_currency),
            "cumulative_recognized_reporting_currency": str(row.cumulative_recognized_reporting_currency),
        }
        for row in rows
    ]
    total_recognized = sum(
        (row.recognized_amount_reporting_currency for row in rows),
        start=Decimal("0.000000"),
    )
    return {
        "run_id": str(run_id),
        "reporting_currency": reporting_currency,
        "rows": payload_rows,
        "count": len(payload_rows),
        "total_recognized_reporting_currency": str(total_recognized),
    }


async def get_contract_drilldown(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
    contract_id: UUID,
) -> dict[str, Any]:
    return await get_contract_drill(
        session,
        tenant_id=tenant_id,
        run_id=run_id,
        contract_id=contract_id,
    )


async def get_obligation_drilldown(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
    obligation_id: UUID,
) -> dict[str, Any]:
    return await get_obligation_drill(
        session,
        tenant_id=tenant_id,
        run_id=run_id,
        obligation_id=obligation_id,
    )


async def get_schedule_drilldown(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
    schedule_id: UUID,
) -> dict[str, Any]:
    return await get_schedule_drill(
        session,
        tenant_id=tenant_id,
        run_id=run_id,
        schedule_id=schedule_id,
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
    return await get_schedule_drilldown(
        session,
        tenant_id=tenant_id,
        run_id=run_id,
        schedule_id=record_id,
    )


def register_workflow() -> type[Any]:
    from financeops.temporal.revenue_workflows import RevenueRecognitionWorkflow

    return RevenueRecognitionWorkflow
