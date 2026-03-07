from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import NotFoundError, ValidationError
from financeops.db.models.prepaid import (
    PrepaidAdjustment,
    PrepaidAmortizationSchedule,
    PrepaidJournalEntry,
    PrepaidRun,
    PrepaidRunEvent,
)
from financeops.schemas.prepaid import PrepaidRunRequest
from financeops.services.accounting_common.quantization_policy import quantize_persisted_amount
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
from financeops.services.prepaid.adjustments import (
    build_schedule_version_token,
    persist_adjustments,
    resolve_effective_version_token,
)
from financeops.services.prepaid.drilldown_service import (
    get_journal_drill,
    get_prepaid_drill,
    get_schedule_drill,
)
from financeops.services.prepaid.journal_builder import build_prepaid_journal_preview
from financeops.services.prepaid.lineage_validation import validate_prepaid_lineage
from financeops.services.prepaid.pattern_resolver import normalize_pattern
from financeops.services.prepaid.prepaid_registry import register_prepaids
from financeops.services.prepaid.schedule_generator import MissingLockedRateError, generate_schedule_rows

_AUDIT_NAMESPACE = "prepaid"


def _decimal_text(value: Decimal) -> str:
    return f"{quantize_persisted_amount(value):.6f}"


def _canonical_request_payload(payload: PrepaidRunRequest) -> dict[str, Any]:
    canonical_prepaids: list[dict[str, Any]] = []
    for prepaid in sorted(payload.prepaids, key=lambda item: item.prepaid_code):
        normalized_pattern = normalize_pattern(prepaid)
        canonical_prepaids.append(
            {
                "prepaid_code": prepaid.prepaid_code,
                "description": prepaid.description,
                "prepaid_currency": prepaid.prepaid_currency,
                "reporting_currency": prepaid.reporting_currency,
                "term_start_date": prepaid.term_start_date.isoformat(),
                "term_end_date": prepaid.term_end_date.isoformat(),
                "base_amount_contract_currency": _decimal_text(prepaid.base_amount_contract_currency),
                "period_frequency": "monthly",
                "pattern_type": prepaid.pattern_type.value,
                "periods": normalized_pattern.canonical_json["periods"],
                "rate_mode": prepaid.rate_mode.value,
                "source_expense_reference": prepaid.source_expense_reference,
                "parent_reference_id": str(prepaid.parent_reference_id) if prepaid.parent_reference_id else None,
                "source_reference_id": str(prepaid.source_reference_id) if prepaid.source_reference_id else None,
                "adjustments": [
                    {
                        "effective_date": item.effective_date.isoformat(),
                        "adjustment_type": item.adjustment_type,
                        "adjustment_reason": item.adjustment_reason,
                        "idempotency_key": item.idempotency_key,
                        "catch_up_amount_reporting_currency": _decimal_text(
                            item.catch_up_amount_reporting_currency
                        ),
                    }
                    for item in sorted(
                        prepaid.adjustments,
                        key=lambda row: (row.effective_date, row.adjustment_type, row.idempotency_key),
                    )
                ],
            }
        )

    return {
        "period_year": payload.period_year,
        "period_month": payload.period_month,
        "prepaids": canonical_prepaids,
    }


async def _get_run_or_raise(session: AsyncSession, *, tenant_id: UUID, run_id: UUID) -> PrepaidRun:
    result = await session.execute(
        select(PrepaidRun).where(
            PrepaidRun.tenant_id == tenant_id,
            PrepaidRun.id == run_id,
        )
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise NotFoundError("Prepaid run not found")
    return run


def _parse_request(configuration_json: dict[str, Any]) -> PrepaidRunRequest:
    return PrepaidRunRequest.model_validate(configuration_json)


async def create_run(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    initiated_by: UUID,
    request_payload: dict[str, Any],
    correlation_id: str,
) -> dict[str, Any]:
    payload = PrepaidRunRequest.model_validate(request_payload)
    canonical_payload = _canonical_request_payload(payload)
    signature = build_request_signature(canonical_payload)
    workflow_id = f"prepaid-{signature[:24]}"

    result = await create_run_header(
        session,
        run_model=PrepaidRun,
        event_model=PrepaidRunEvent,
        tenant_id=tenant_id,
        initiated_by=initiated_by,
        request_payload=canonical_payload,
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
) -> PrepaidRunEvent:
    return await append_event(
        session,
        event_model=PrepaidRunEvent,
        tenant_id=tenant_id,
        run_id=run_id,
        user_id=user_id,
        event_type=RUN_EVENT_RUNNING,
        idempotency_key="stage-running",
        metadata_json=None,
        correlation_id=correlation_id,
        audit_namespace=_AUDIT_NAMESPACE,
    )


async def load_prepaids_for_run(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
    user_id: UUID,
    correlation_id: str,
) -> dict[str, int]:
    run = await _get_run_or_raise(session, tenant_id=tenant_id, run_id=run_id)
    payload = _parse_request(run.configuration_json)
    registered = await register_prepaids(
        session,
        tenant_id=tenant_id,
        user_id=user_id,
        correlation_id=correlation_id,
        prepaids=payload.prepaids,
    )
    return {"prepaid_count": len(registered)}


async def resolve_amortization_pattern_for_run(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
) -> dict[str, int]:
    run = await _get_run_or_raise(session, tenant_id=tenant_id, run_id=run_id)
    payload = _parse_request(run.configuration_json)

    period_count = 0
    for prepaid in payload.prepaids:
        normalized = normalize_pattern(prepaid)
        period_count += len(normalized.periods)
    return {"pattern_count": len(payload.prepaids), "period_count": period_count}


async def generate_amortization_schedule_for_run(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
    user_id: UUID,
    correlation_id: str,
) -> dict[str, int]:
    run = await _get_run_or_raise(session, tenant_id=tenant_id, run_id=run_id)
    payload = _parse_request(run.configuration_json)
    registered = await register_prepaids(
        session,
        tenant_id=tenant_id,
        user_id=user_id,
        correlation_id=correlation_id,
        prepaids=payload.prepaids,
    )

    adjustment_map: dict[UUID, list] = {}
    total_adjustments = 0
    for prepaid in registered:
        root_token = build_schedule_version_token(
            prepaid_id=prepaid.prepaid_id,
            pattern_normalized_json=prepaid.normalized_pattern.canonical_json,
            reporting_currency=prepaid.reporting_currency,
            rate_mode=prepaid.rate_mode,
            adjustment_effective_date=prepaid.term_start_date,
            prior_schedule_version_token_or_root="root",
        )
        persisted_adjustments = await persist_adjustments(
            session,
            tenant_id=tenant_id,
            run_id=run_id,
            prepaid_id=prepaid.prepaid_id,
            source_expense_reference=prepaid.source_expense_reference,
            parent_reference_id=prepaid.parent_reference_id,
            source_reference_id=prepaid.source_reference_id,
            correlation_id=correlation_id,
            user_id=user_id,
            adjustments=prepaid.adjustments,
            root_schedule_version_token=root_token,
            pattern_normalized_json=prepaid.normalized_pattern.canonical_json,
            reporting_currency=prepaid.reporting_currency,
            rate_mode=prepaid.rate_mode,
        )
        adjustment_map[prepaid.prepaid_id] = persisted_adjustments
        total_adjustments += len(persisted_adjustments)

    generated = await generate_schedule_rows(
        session,
        tenant_id=tenant_id,
        prepaids=registered,
        adjustment_map=adjustment_map,
    )

    inserted = 0
    for row in generated.rows:
        existing = await session.execute(
            select(PrepaidAmortizationSchedule).where(
                PrepaidAmortizationSchedule.tenant_id == tenant_id,
                PrepaidAmortizationSchedule.run_id == run_id,
                PrepaidAmortizationSchedule.prepaid_id == row.prepaid_id,
                PrepaidAmortizationSchedule.amortization_date == row.amortization_date,
                PrepaidAmortizationSchedule.schedule_version_token == row.schedule_version_token,
                PrepaidAmortizationSchedule.period_seq == row.period_seq,
            )
        )
        if existing.scalar_one_or_none() is not None:
            continue

        await AuditWriter.insert_financial_record(
            session,
            model_class=PrepaidAmortizationSchedule,
            tenant_id=tenant_id,
            record_data={
                "run_id": str(run_id),
                "prepaid_id": str(row.prepaid_id),
                "period_seq": row.period_seq,
                "amortization_date": row.amortization_date.isoformat(),
                "schedule_version_token": row.schedule_version_token,
            },
            values={
                "run_id": run_id,
                "prepaid_id": row.prepaid_id,
                "period_seq": row.period_seq,
                "amortization_date": row.amortization_date,
                "recognition_period_year": row.recognition_period_year,
                "recognition_period_month": row.recognition_period_month,
                "schedule_version_token": row.schedule_version_token,
                "base_amount_contract_currency": row.base_amount_contract_currency,
                "amortized_amount_reporting_currency": row.amortized_amount_reporting_currency,
                "cumulative_amortized_reporting_currency": row.cumulative_amortized_reporting_currency,
                "fx_rate_used": row.fx_rate_used,
                "fx_rate_date": row.fx_rate_date,
                "fx_rate_source": row.fx_rate_source,
                "schedule_status": row.schedule_status,
                "source_expense_reference": row.source_expense_reference,
                "parent_reference_id": row.parent_reference_id,
                "source_reference_id": row.source_reference_id,
                "correlation_id": correlation_id,
            },
            audit=AuditEvent(
                tenant_id=tenant_id,
                user_id=user_id,
                action="prepaid.schedule.created",
                resource_type="prepaid_amortization_schedule",
                new_value={
                    "run_id": str(run_id),
                    "prepaid_id": str(row.prepaid_id),
                    "period_seq": row.period_seq,
                    "schedule_version_token": row.schedule_version_token,
                    "correlation_id": correlation_id,
                },
            ),
        )
        inserted += 1

    return {"schedule_count": inserted, "adjustment_count": total_adjustments}


async def build_journal_preview_for_run(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
    user_id: UUID,
    correlation_id: str,
) -> dict[str, int]:
    prepaid_ids = (
        await session.execute(
            select(PrepaidAmortizationSchedule.prepaid_id)
            .where(
                PrepaidAmortizationSchedule.tenant_id == tenant_id,
                PrepaidAmortizationSchedule.run_id == run_id,
            )
            .distinct()
            .order_by(PrepaidAmortizationSchedule.prepaid_id)
        )
    ).scalars().all()

    effective_tokens: dict[UUID, str] = {}
    for prepaid_id in prepaid_ids:
        root_token = await _resolve_root_version_token(
            session,
            tenant_id=tenant_id,
            run_id=run_id,
            prepaid_id=prepaid_id,
        )
        if root_token is None:
            continue
        effective_tokens[prepaid_id] = await resolve_effective_version_token(
            session,
            tenant_id=tenant_id,
            run_id=run_id,
            prepaid_id=prepaid_id,
            root_schedule_version_token=root_token,
        )

    schedules: list[PrepaidAmortizationSchedule] = []
    for prepaid_id, token in effective_tokens.items():
        schedules.extend(
            (
                await session.execute(
                    select(PrepaidAmortizationSchedule)
                    .where(
                        PrepaidAmortizationSchedule.tenant_id == tenant_id,
                        PrepaidAmortizationSchedule.run_id == run_id,
                        PrepaidAmortizationSchedule.prepaid_id == prepaid_id,
                        PrepaidAmortizationSchedule.schedule_version_token == token,
                    )
                    .order_by(
                        PrepaidAmortizationSchedule.amortization_date,
                        PrepaidAmortizationSchedule.prepaid_id,
                        PrepaidAmortizationSchedule.period_seq,
                        PrepaidAmortizationSchedule.id,
                    )
                )
            ).scalars().all()
        )
    schedules.sort(
        key=lambda row: (
            row.amortization_date,
            str(row.prepaid_id),
            row.period_seq,
            str(row.id),
        )
    )

    preview_rows = build_prepaid_journal_preview(
        run_id=run_id,
        schedule_rows=list(schedules),
    )
    inserted = 0
    for row in preview_rows:
        existing = await session.execute(
            select(PrepaidJournalEntry).where(
                PrepaidJournalEntry.tenant_id == tenant_id,
                PrepaidJournalEntry.run_id == run_id,
                PrepaidJournalEntry.schedule_id == row.schedule_id,
            )
        )
        if existing.scalar_one_or_none() is not None:
            continue

        await AuditWriter.insert_financial_record(
            session,
            model_class=PrepaidJournalEntry,
            tenant_id=tenant_id,
            record_data={
                "run_id": str(run_id),
                "prepaid_id": str(row.prepaid_id),
                "schedule_id": str(row.schedule_id),
                "journal_reference": row.journal_reference,
            },
            values={
                "run_id": run_id,
                "prepaid_id": row.prepaid_id,
                "schedule_id": row.schedule_id,
                "journal_reference": row.journal_reference,
                "entry_date": row.entry_date,
                "debit_account": row.debit_account,
                "credit_account": row.credit_account,
                "amount_reporting_currency": row.amount_reporting_currency,
                "source_expense_reference": row.source_expense_reference,
                "parent_reference_id": row.parent_reference_id,
                "source_reference_id": row.source_reference_id,
                "correlation_id": correlation_id,
            },
            audit=AuditEvent(
                tenant_id=tenant_id,
                user_id=user_id,
                action="prepaid.journal.preview.created",
                resource_type="prepaid_journal_entry",
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
    result = await validate_prepaid_lineage(
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
) -> PrepaidRunEvent:
    if event_type not in TERMINAL_EVENT_TYPES:
        raise AccountingValidationError(
            error_code=INVALID_EVENT_SEQUENCE,
            message="Invalid terminal run event type",
        )

    if event_type in {RUN_EVENT_COMPLETED, RUN_EVENT_COMPLETED_WITH_WARNINGS}:
        await validate_lineage_before_finalize(
            session,
            event_model=PrepaidRunEvent,
            tenant_id=tenant_id,
            run_id=run_id,
            user_id=user_id,
            correlation_id=correlation_id,
            audit_namespace=_AUDIT_NAMESPACE,
            lineage_validator=lambda: validate_prepaid_lineage(
                session,
                tenant_id=tenant_id,
                run_id=run_id,
            ),
        )

    existing_terminal = await session.execute(
        select(PrepaidRunEvent)
        .where(
            PrepaidRunEvent.tenant_id == tenant_id,
            PrepaidRunEvent.run_id == run_id,
            PrepaidRunEvent.event_type.in_(list(TERMINAL_EVENT_TYPES)),
        )
        .order_by(desc(PrepaidRunEvent.event_seq))
        .limit(1)
    )
    terminal = existing_terminal.scalar_one_or_none()
    if terminal is not None:
        return terminal

    return await append_event(
        session,
        event_model=PrepaidRunEvent,
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
        run_model=PrepaidRun,
        event_model=PrepaidRunEvent,
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


async def _resolve_root_version_token(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
    prepaid_id: UUID,
) -> str | None:
    first_adjustment = await session.execute(
        select(PrepaidAdjustment)
        .where(
            PrepaidAdjustment.tenant_id == tenant_id,
            PrepaidAdjustment.run_id == run_id,
            PrepaidAdjustment.prepaid_id == prepaid_id,
        )
        .order_by(
            PrepaidAdjustment.effective_date,
            PrepaidAdjustment.created_at,
            PrepaidAdjustment.id,
        )
        .limit(1)
    )
    adjustment = first_adjustment.scalar_one_or_none()
    if adjustment is not None:
        return adjustment.prior_schedule_version_token

    first_schedule = await session.execute(
        select(PrepaidAmortizationSchedule.schedule_version_token)
        .where(
            PrepaidAmortizationSchedule.tenant_id == tenant_id,
            PrepaidAmortizationSchedule.run_id == run_id,
            PrepaidAmortizationSchedule.prepaid_id == prepaid_id,
        )
        .order_by(
            PrepaidAmortizationSchedule.created_at,
            PrepaidAmortizationSchedule.period_seq,
            PrepaidAmortizationSchedule.id,
        )
        .limit(1)
    )
    return first_schedule.scalar_one_or_none()


async def get_results(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
) -> dict[str, Any]:
    await _get_run_or_raise(session, tenant_id=tenant_id, run_id=run_id)

    prepaid_ids = (
        await session.execute(
            select(PrepaidAmortizationSchedule.prepaid_id)
            .where(
                PrepaidAmortizationSchedule.tenant_id == tenant_id,
                PrepaidAmortizationSchedule.run_id == run_id,
            )
            .distinct()
            .order_by(PrepaidAmortizationSchedule.prepaid_id)
        )
    ).scalars().all()

    effective_tokens: dict[UUID, str] = {}
    for prepaid_id in prepaid_ids:
        root_token = await _resolve_root_version_token(
            session,
            tenant_id=tenant_id,
            run_id=run_id,
            prepaid_id=prepaid_id,
        )
        if root_token is None:
            continue
        effective_tokens[prepaid_id] = await resolve_effective_version_token(
            session,
            tenant_id=tenant_id,
            run_id=run_id,
            prepaid_id=prepaid_id,
            root_schedule_version_token=root_token,
        )

    rows: list[PrepaidAmortizationSchedule] = []
    for prepaid_id, token in effective_tokens.items():
        rows.extend(
            (
                await session.execute(
                    select(PrepaidAmortizationSchedule)
                    .where(
                        PrepaidAmortizationSchedule.tenant_id == tenant_id,
                        PrepaidAmortizationSchedule.run_id == run_id,
                        PrepaidAmortizationSchedule.prepaid_id == prepaid_id,
                        PrepaidAmortizationSchedule.schedule_version_token == token,
                    )
                    .order_by(
                        PrepaidAmortizationSchedule.prepaid_id,
                        PrepaidAmortizationSchedule.period_seq,
                        PrepaidAmortizationSchedule.amortization_date,
                    )
                )
            ).scalars().all()
        )

    rows.sort(key=lambda row: (str(row.prepaid_id), row.period_seq, row.amortization_date, str(row.id)))
    payload_rows = [
        {
            "schedule_id": str(row.id),
            "prepaid_id": str(row.prepaid_id),
            "period_seq": row.period_seq,
            "amortization_date": row.amortization_date,
            "schedule_version_token": row.schedule_version_token,
            "amortized_amount_reporting_currency": _decimal_text(
                row.amortized_amount_reporting_currency
            ),
            "cumulative_amortized_reporting_currency": _decimal_text(
                row.cumulative_amortized_reporting_currency
            ),
            "fx_rate_used": _decimal_text(row.fx_rate_used),
            "fx_rate_date": row.fx_rate_date,
            "fx_rate_source": row.fx_rate_source,
        }
        for row in rows
    ]
    total = sum((row.amortized_amount_reporting_currency for row in rows), start=Decimal("0.000000"))
    return {
        "run_id": str(run_id),
        "rows": payload_rows,
        "count": len(payload_rows),
        "total_amortized_reporting_currency": _decimal_text(total),
    }


async def get_prepaid_drilldown(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
    prepaid_id: UUID,
) -> dict[str, Any]:
    return await get_prepaid_drill(
        session,
        tenant_id=tenant_id,
        run_id=run_id,
        prepaid_id=prepaid_id,
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
    from financeops.temporal.prepaid_workflows import PrepaidAmortizationWorkflow

    return PrepaidAmortizationWorkflow


__all__ = [
    "MissingLockedRateError",
    "build_journal_preview_for_run",
    "create_run",
    "finalize_run",
    "generate_amortization_schedule_for_run",
    "get_drill",
    "get_journal_drilldown",
    "get_prepaid_drilldown",
    "get_results",
    "get_run_status",
    "get_schedule_drilldown",
    "load_prepaids_for_run",
    "mark_run_running",
    "register_workflow",
    "resolve_amortization_pattern_for_run",
    "validate_lineage_for_run",
]
