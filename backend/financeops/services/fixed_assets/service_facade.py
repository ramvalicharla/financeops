from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import NotFoundError
from financeops.db.models.fixed_assets import (
    AssetDepreciationSchedule,
    AssetDisposal,
    AssetImpairment,
    AssetJournalEntry,
    FarRun,
    FarRunEvent,
)
from financeops.schemas.fixed_assets import FarRunRequest
from financeops.services.accounting_common.accounting_errors import AccountingValidationError
from financeops.services.accounting_common.error_codes import (
    INVALID_EVENT_SEQUENCE,
    LINEAGE_INCOMPLETE,
)
from financeops.services.accounting_common.quantization_policy import quantize_persisted_amount
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
from financeops.services.fixed_assets.asset_registry import register_assets
from financeops.services.fixed_assets.depreciation_engine import (
    GeneratedDepreciationRow,
    MissingLockedRateError,
    build_schedule_version_token,
    generate_base_depreciation_rows,
)
from financeops.services.fixed_assets.disposal_handler import apply_disposals
from financeops.services.fixed_assets.drilldown_service import (
    get_asset_drill,
    get_depreciation_drill,
    get_disposal_drill,
    get_impairment_drill,
    get_journal_drill,
)
from financeops.services.fixed_assets.impairment_handler import apply_impairments
from financeops.services.fixed_assets.journal_builder import build_far_journal_preview
from financeops.services.fixed_assets.lineage_validation import validate_fixed_assets_lineage

_AUDIT_NAMESPACE = "fixed_assets"


def _decimal_text(value: Decimal) -> str:
    return f"{quantize_persisted_amount(value):.6f}"


def _canonical_request_payload(payload: FarRunRequest) -> dict[str, Any]:
    canonical_assets: list[dict[str, Any]] = []
    for asset in sorted(payload.assets, key=lambda row: row.asset_code):
        canonical_assets.append(
            {
                "asset_code": asset.asset_code,
                "description": asset.description,
                "entity_id": asset.entity_id,
                "asset_class": asset.asset_class,
                "asset_currency": asset.asset_currency,
                "reporting_currency": asset.reporting_currency,
                "capitalization_date": asset.capitalization_date.isoformat(),
                "in_service_date": asset.in_service_date.isoformat(),
                "capitalized_amount_asset_currency": _decimal_text(asset.capitalized_amount_asset_currency),
                "depreciation_method": asset.depreciation_method.value,
                "useful_life_months": asset.useful_life_months,
                "reducing_balance_rate_annual": (
                    _decimal_text(asset.reducing_balance_rate_annual)
                    if asset.reducing_balance_rate_annual is not None
                    else None
                ),
                "residual_value_reporting_currency": _decimal_text(asset.residual_value_reporting_currency),
                "rate_mode": asset.rate_mode.value,
                "source_acquisition_reference": asset.source_acquisition_reference,
                "parent_reference_id": str(asset.parent_reference_id) if asset.parent_reference_id else None,
                "source_reference_id": str(asset.source_reference_id) if asset.source_reference_id else None,
                "impairments": [
                    {
                        "impairment_date": item.impairment_date.isoformat(),
                        "impairment_amount_reporting_currency": _decimal_text(
                            item.impairment_amount_reporting_currency
                        ),
                        "idempotency_key": item.idempotency_key,
                        "reason": item.reason,
                    }
                    for item in sorted(
                        asset.impairments, key=lambda row: (row.impairment_date, row.idempotency_key)
                    )
                ],
                "disposals": [
                    {
                        "disposal_date": item.disposal_date.isoformat(),
                        "proceeds_reporting_currency": _decimal_text(item.proceeds_reporting_currency),
                        "disposal_cost_reporting_currency": _decimal_text(item.disposal_cost_reporting_currency),
                        "idempotency_key": item.idempotency_key,
                    }
                    for item in sorted(
                        asset.disposals, key=lambda row: (row.disposal_date, row.idempotency_key)
                    )
                ],
            }
        )
    return {
        "period_year": payload.period_year,
        "period_month": payload.period_month,
        "assets": canonical_assets,
    }


async def _get_run_or_raise(session: AsyncSession, *, tenant_id: UUID, run_id: UUID) -> FarRun:
    result = await session.execute(
        select(FarRun).where(
            FarRun.tenant_id == tenant_id,
            FarRun.id == run_id,
        )
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise NotFoundError("Fixed-assets run not found")
    return run


def _parse_request(configuration_json: dict[str, Any]) -> FarRunRequest:
    return FarRunRequest.model_validate(configuration_json)


async def _insert_schedule_rows(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
    user_id: UUID,
    correlation_id: str,
    rows: list[GeneratedDepreciationRow],
) -> int:
    inserted = 0
    for row in rows:
        existing = await session.execute(
            select(AssetDepreciationSchedule).where(
                AssetDepreciationSchedule.tenant_id == tenant_id,
                AssetDepreciationSchedule.run_id == run_id,
                AssetDepreciationSchedule.asset_id == row.asset_id,
                AssetDepreciationSchedule.depreciation_date == row.depreciation_date,
                AssetDepreciationSchedule.schedule_version_token == row.schedule_version_token,
                AssetDepreciationSchedule.period_seq == row.period_seq,
            )
        )
        if existing.scalar_one_or_none() is not None:
            continue

        await AuditWriter.insert_financial_record(
            session,
            model_class=AssetDepreciationSchedule,
            tenant_id=tenant_id,
            record_data={
                "run_id": str(run_id),
                "asset_id": str(row.asset_id),
                "period_seq": row.period_seq,
                "depreciation_date": row.depreciation_date.isoformat(),
                "schedule_version_token": row.schedule_version_token,
            },
            values={
                "run_id": run_id,
                "asset_id": row.asset_id,
                "period_seq": row.period_seq,
                "depreciation_date": row.depreciation_date,
                "depreciation_period_year": row.depreciation_period_year,
                "depreciation_period_month": row.depreciation_period_month,
                "schedule_version_token": row.schedule_version_token,
                "opening_carrying_amount_reporting_currency": row.opening_carrying_amount_reporting_currency,
                "depreciation_amount_reporting_currency": row.depreciation_amount_reporting_currency,
                "cumulative_depreciation_reporting_currency": row.cumulative_depreciation_reporting_currency,
                "closing_carrying_amount_reporting_currency": row.closing_carrying_amount_reporting_currency,
                "fx_rate_used": row.fx_rate_used,
                "fx_rate_date": row.fx_rate_date,
                "fx_rate_source": row.fx_rate_source,
                "schedule_status": row.schedule_status,
                "source_acquisition_reference": row.source_acquisition_reference,
                "parent_reference_id": row.parent_reference_id,
                "source_reference_id": row.source_reference_id,
                "correlation_id": correlation_id,
            },
            audit=AuditEvent(
                tenant_id=tenant_id,
                user_id=user_id,
                action="fixed_assets.schedule.created",
                resource_type="asset_depreciation_schedule",
            ),
        )
        inserted += 1
    return inserted


async def create_run(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    initiated_by: UUID,
    request_payload: dict[str, Any],
    correlation_id: str,
) -> dict[str, Any]:
    payload = FarRunRequest.model_validate(request_payload)
    canonical_payload = _canonical_request_payload(payload)
    signature = build_request_signature(canonical_payload)
    workflow_id = f"fixed-assets-{signature[:24]}"

    result = await create_run_header(
        session,
        run_model=FarRun,
        event_model=FarRunEvent,
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
) -> FarRunEvent:
    return await append_event(
        session,
        event_model=FarRunEvent,
        tenant_id=tenant_id,
        run_id=run_id,
        user_id=user_id,
        event_type=RUN_EVENT_RUNNING,
        idempotency_key="stage-running",
        metadata_json=None,
        correlation_id=correlation_id,
        audit_namespace=_AUDIT_NAMESPACE,
    )


async def load_assets_for_run(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
    user_id: UUID,
    correlation_id: str,
) -> dict[str, int]:
    run = await _get_run_or_raise(session, tenant_id=tenant_id, run_id=run_id)
    payload = _parse_request(run.configuration_json)
    registered = await register_assets(
        session,
        tenant_id=tenant_id,
        user_id=user_id,
        correlation_id=correlation_id,
        accepted_at=run.created_at,
        assets=payload.assets,
    )
    return {"asset_count": len(registered)}


async def generate_depreciation_schedule_for_run(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
    user_id: UUID,
    correlation_id: str,
) -> dict[str, int]:
    run = await _get_run_or_raise(session, tenant_id=tenant_id, run_id=run_id)
    payload = _parse_request(run.configuration_json)
    registered = await register_assets(
        session,
        tenant_id=tenant_id,
        user_id=user_id,
        correlation_id=correlation_id,
        accepted_at=run.created_at,
        assets=payload.assets,
    )

    generated = await generate_base_depreciation_rows(
        session,
        tenant_id=tenant_id,
        assets=registered,
    )
    inserted = await _insert_schedule_rows(
        session,
        tenant_id=tenant_id,
        run_id=run_id,
        user_id=user_id,
        correlation_id=correlation_id,
        rows=generated.rows,
    )
    return {"schedule_count": inserted}


async def apply_impairment_and_disposal_events_for_run(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
    user_id: UUID,
    correlation_id: str,
) -> dict[str, int]:
    run = await _get_run_or_raise(session, tenant_id=tenant_id, run_id=run_id)
    payload = _parse_request(run.configuration_json)
    registered = await register_assets(
        session,
        tenant_id=tenant_id,
        user_id=user_id,
        correlation_id=correlation_id,
        accepted_at=run.created_at,
        assets=payload.assets,
    )

    regenerated_inserted = 0
    impairment_count = 0
    disposal_count = 0

    for asset in registered:
        root_token_result = await session.execute(
            select(AssetDepreciationSchedule.schedule_version_token)
            .where(
                AssetDepreciationSchedule.tenant_id == tenant_id,
                AssetDepreciationSchedule.run_id == run_id,
                AssetDepreciationSchedule.asset_id == asset.asset_id,
            )
            .order_by(
                AssetDepreciationSchedule.created_at,
                AssetDepreciationSchedule.period_seq,
                AssetDepreciationSchedule.id,
            )
            .limit(1)
        )
        root_token = root_token_result.scalar_one_or_none()
        if root_token is None:
            root_token = build_schedule_version_token(
                asset_id=asset.asset_id,
                depreciation_method=asset.depreciation_method,
                useful_life_months=asset.useful_life_months,
                reducing_balance_rate_annual=asset.reducing_balance_rate_annual,
                residual_value_reporting_currency=asset.residual_value_reporting_currency,
                reporting_currency=asset.reporting_currency,
                rate_mode=asset.rate_mode,
                effective_date=asset.in_service_date,
                prior_schedule_version_token_or_root="root",
            )

        base_rows_result = await session.execute(
            select(AssetDepreciationSchedule)
            .where(
                AssetDepreciationSchedule.tenant_id == tenant_id,
                AssetDepreciationSchedule.run_id == run_id,
                AssetDepreciationSchedule.asset_id == asset.asset_id,
                AssetDepreciationSchedule.schedule_version_token == root_token,
            )
            .order_by(
                AssetDepreciationSchedule.depreciation_date,
                AssetDepreciationSchedule.period_seq,
                AssetDepreciationSchedule.id,
            )
        )
        base_rows = [
            GeneratedDepreciationRow(
                asset_id=row.asset_id,
                period_seq=row.period_seq,
                depreciation_date=row.depreciation_date,
                depreciation_period_year=row.depreciation_period_year,
                depreciation_period_month=row.depreciation_period_month,
                schedule_version_token=row.schedule_version_token,
                opening_carrying_amount_reporting_currency=row.opening_carrying_amount_reporting_currency,
                depreciation_amount_reporting_currency=row.depreciation_amount_reporting_currency,
                cumulative_depreciation_reporting_currency=row.cumulative_depreciation_reporting_currency,
                closing_carrying_amount_reporting_currency=row.closing_carrying_amount_reporting_currency,
                fx_rate_used=row.fx_rate_used,
                fx_rate_date=row.fx_rate_date,
                fx_rate_source=row.fx_rate_source,
                schedule_status=row.schedule_status,
                source_acquisition_reference=row.source_acquisition_reference,
                parent_reference_id=row.parent_reference_id,
                source_reference_id=row.source_reference_id,
            )
            for row in base_rows_result.scalars().all()
        ]

        combined_events = [(item.impairment_date, 1, "impairment") for item in asset.impairments] + [
            (item.disposal_date, 2, "disposal") for item in asset.disposals
        ]
        seen_disposal_date = None
        for event_date, _priority, event_type in sorted(combined_events, key=lambda row: (row[0], row[1])):
            if seen_disposal_date is not None and event_date > seen_disposal_date:
                raise AccountingValidationError(
                    error_code=INVALID_EVENT_SEQUENCE,
                    message="disposal on date D blocks any subsequent impairment/disposal with date > D",
                )
            if event_type == "disposal":
                seen_disposal_date = event_date

        impairment_result = await apply_impairments(
            session,
            tenant_id=tenant_id,
            run_id=run_id,
            user_id=user_id,
            correlation_id=correlation_id,
            asset_id=asset.asset_id,
            source_acquisition_reference=asset.source_acquisition_reference,
            parent_reference_id=asset.parent_reference_id,
            source_reference_id=asset.source_reference_id,
            depreciation_method=asset.depreciation_method,
            useful_life_months=asset.useful_life_months,
            reducing_balance_rate_annual=asset.reducing_balance_rate_annual,
            residual_value_reporting_currency=asset.residual_value_reporting_currency,
            reporting_currency=asset.reporting_currency,
            rate_mode=asset.rate_mode,
            current_rows=base_rows,
            events=asset.impairments,
            prior_schedule_version_token=root_token,
        )
        impairment_count += len(impairment_result.events)

        disposal_result = await apply_disposals(
            session,
            tenant_id=tenant_id,
            run_id=run_id,
            user_id=user_id,
            correlation_id=correlation_id,
            asset_id=asset.asset_id,
            source_acquisition_reference=asset.source_acquisition_reference,
            parent_reference_id=asset.parent_reference_id,
            source_reference_id=asset.source_reference_id,
            depreciation_method=asset.depreciation_method,
            useful_life_months=asset.useful_life_months,
            reducing_balance_rate_annual=asset.reducing_balance_rate_annual,
            residual_value_reporting_currency=asset.residual_value_reporting_currency,
            reporting_currency=asset.reporting_currency,
            rate_mode=asset.rate_mode,
            current_rows=impairment_result.rows,
            disposals=asset.disposals,
            prior_schedule_version_token=impairment_result.latest_schedule_version_token,
        )
        disposal_count += len(disposal_result.events)

        regenerated_rows = [
            row
            for row in disposal_result.rows
            if row.schedule_version_token not in {root_token, impairment_result.latest_schedule_version_token}
            or row.schedule_status in {"regenerated", "disposed_partial"}
        ]
        regenerated_inserted += await _insert_schedule_rows(
            session,
            tenant_id=tenant_id,
            run_id=run_id,
            user_id=user_id,
            correlation_id=correlation_id,
            rows=regenerated_rows,
        )

    return {
        "impairment_count": impairment_count,
        "disposal_count": disposal_count,
        "regenerated_schedule_count": regenerated_inserted,
    }


async def build_journal_preview_for_run(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
    user_id: UUID,
    correlation_id: str,
) -> dict[str, int]:
    asset_ids = (
        await session.execute(
            select(AssetDepreciationSchedule.asset_id)
            .where(
                AssetDepreciationSchedule.tenant_id == tenant_id,
                AssetDepreciationSchedule.run_id == run_id,
            )
            .distinct()
            .order_by(AssetDepreciationSchedule.asset_id)
        )
    ).scalars().all()

    effective_tokens: dict[UUID, str] = {}
    for asset_id in asset_ids:
        root_token = await _resolve_root_version_token(
            session,
            tenant_id=tenant_id,
            run_id=run_id,
            asset_id=asset_id,
        )
        if root_token is None:
            continue
        effective_tokens[asset_id] = await _resolve_effective_version_token(
            session,
            tenant_id=tenant_id,
            run_id=run_id,
            asset_id=asset_id,
            root_schedule_version_token=root_token,
        )

    schedule_rows: list[AssetDepreciationSchedule] = []
    for asset_id, token in effective_tokens.items():
        schedule_rows.extend(
            (
                await session.execute(
                    select(AssetDepreciationSchedule)
                    .where(
                        AssetDepreciationSchedule.tenant_id == tenant_id,
                        AssetDepreciationSchedule.run_id == run_id,
                        AssetDepreciationSchedule.asset_id == asset_id,
                        AssetDepreciationSchedule.schedule_version_token == token,
                    )
                    .order_by(
                        AssetDepreciationSchedule.asset_id,
                        AssetDepreciationSchedule.depreciation_date,
                        AssetDepreciationSchedule.period_seq,
                        AssetDepreciationSchedule.id,
                    )
                )
            ).scalars().all()
        )

    impairments = (
        await session.execute(
            select(AssetImpairment)
            .where(
                AssetImpairment.tenant_id == tenant_id,
                AssetImpairment.run_id == run_id,
            )
            .order_by(
                AssetImpairment.impairment_date,
                AssetImpairment.created_at,
                AssetImpairment.id,
            )
        )
    ).scalars().all()
    disposals = (
        await session.execute(
            select(AssetDisposal)
            .where(
                AssetDisposal.tenant_id == tenant_id,
                AssetDisposal.run_id == run_id,
            )
            .order_by(
                AssetDisposal.disposal_date,
                AssetDisposal.created_at,
                AssetDisposal.id,
            )
        )
    ).scalars().all()

    preview_rows = build_far_journal_preview(
        run_id=run_id,
        schedule_rows=list(schedule_rows),
        impairment_rows=list(impairments),
        disposal_rows=list(disposals),
    )
    inserted = 0
    for row in preview_rows:
        existing = await session.execute(
            select(AssetJournalEntry).where(
                AssetJournalEntry.tenant_id == tenant_id,
                AssetJournalEntry.run_id == run_id,
                AssetJournalEntry.journal_reference == row.journal_reference,
                AssetJournalEntry.line_seq == row.line_seq,
            )
        )
        if existing.scalar_one_or_none() is not None:
            continue
        await AuditWriter.insert_financial_record(
            session,
            model_class=AssetJournalEntry,
            tenant_id=tenant_id,
            record_data={
                "run_id": str(run_id),
                "asset_id": str(row.asset_id),
                "journal_reference": row.journal_reference,
                "line_seq": row.line_seq,
            },
            values={
                "run_id": run_id,
                "asset_id": row.asset_id,
                "depreciation_schedule_id": row.depreciation_schedule_id,
                "impairment_id": row.impairment_id,
                "disposal_id": row.disposal_id,
                "journal_reference": row.journal_reference,
                "line_seq": row.line_seq,
                "entry_date": row.entry_date,
                "debit_account": row.debit_account,
                "credit_account": row.credit_account,
                "amount_reporting_currency": row.amount_reporting_currency,
                "source_acquisition_reference": row.source_acquisition_reference,
                "parent_reference_id": row.parent_reference_id,
                "source_reference_id": row.source_reference_id,
                "correlation_id": correlation_id,
            },
            audit=AuditEvent(
                tenant_id=tenant_id,
                user_id=user_id,
                action="fixed_assets.journal.preview.created",
                resource_type="asset_journal_entry",
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
    result = await validate_fixed_assets_lineage(
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
) -> FarRunEvent:
    if event_type not in TERMINAL_EVENT_TYPES:
        raise AccountingValidationError(
            error_code=INVALID_EVENT_SEQUENCE,
            message="Invalid terminal run event type",
        )

    if event_type in {RUN_EVENT_COMPLETED, RUN_EVENT_COMPLETED_WITH_WARNINGS}:
        await validate_lineage_before_finalize(
            session,
            event_model=FarRunEvent,
            tenant_id=tenant_id,
            run_id=run_id,
            user_id=user_id,
            correlation_id=correlation_id,
            audit_namespace=_AUDIT_NAMESPACE,
            lineage_validator=lambda: validate_fixed_assets_lineage(
                session,
                tenant_id=tenant_id,
                run_id=run_id,
            ),
        )

    existing_terminal = await session.execute(
        select(FarRunEvent)
        .where(
            FarRunEvent.tenant_id == tenant_id,
            FarRunEvent.run_id == run_id,
            FarRunEvent.event_type.in_(list(TERMINAL_EVENT_TYPES)),
        )
        .order_by(desc(FarRunEvent.event_seq))
        .limit(1)
    )
    terminal = existing_terminal.scalar_one_or_none()
    if terminal is not None:
        return terminal

    return await append_event(
        session,
        event_model=FarRunEvent,
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
        run_model=FarRun,
        event_model=FarRunEvent,
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
    asset_id: UUID,
) -> str | None:
    first_impairment = (
        await session.execute(
            select(AssetImpairment)
            .where(
                AssetImpairment.tenant_id == tenant_id,
                AssetImpairment.run_id == run_id,
                AssetImpairment.asset_id == asset_id,
            )
            .order_by(
                AssetImpairment.impairment_date,
                AssetImpairment.created_at,
                AssetImpairment.id,
            )
            .limit(1)
        )
    ).scalar_one_or_none()

    first_disposal = (
        await session.execute(
            select(AssetDisposal)
            .where(
                AssetDisposal.tenant_id == tenant_id,
                AssetDisposal.run_id == run_id,
                AssetDisposal.asset_id == asset_id,
            )
            .order_by(
                AssetDisposal.disposal_date,
                AssetDisposal.created_at,
                AssetDisposal.id,
            )
            .limit(1)
        )
    ).scalar_one_or_none()

    root_from_event: str | None = None
    if first_impairment is not None and first_disposal is not None:
        imp_key = (first_impairment.impairment_date, 1, first_impairment.created_at, first_impairment.id)
        disp_key = (first_disposal.disposal_date, 2, first_disposal.created_at, first_disposal.id)
        root_from_event = (
            first_impairment.prior_schedule_version_token
            if imp_key <= disp_key
            else first_disposal.prior_schedule_version_token
        )
    elif first_impairment is not None:
        root_from_event = first_impairment.prior_schedule_version_token
    elif first_disposal is not None:
        root_from_event = first_disposal.prior_schedule_version_token

    if root_from_event:
        return root_from_event

    first_schedule = await session.execute(
        select(AssetDepreciationSchedule.schedule_version_token)
        .where(
            AssetDepreciationSchedule.tenant_id == tenant_id,
            AssetDepreciationSchedule.run_id == run_id,
            AssetDepreciationSchedule.asset_id == asset_id,
        )
        .order_by(
            AssetDepreciationSchedule.created_at,
            AssetDepreciationSchedule.period_seq,
            AssetDepreciationSchedule.id,
        )
        .limit(1)
    )
    return first_schedule.scalar_one_or_none()


async def _resolve_effective_version_token(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
    asset_id: UUID,
    root_schedule_version_token: str,
) -> str:
    latest_impairment = (
        await session.execute(
            select(AssetImpairment)
            .where(
                AssetImpairment.tenant_id == tenant_id,
                AssetImpairment.run_id == run_id,
                AssetImpairment.asset_id == asset_id,
            )
            .order_by(
                desc(AssetImpairment.impairment_date),
                desc(AssetImpairment.created_at),
                desc(AssetImpairment.id),
            )
            .limit(1)
        )
    ).scalar_one_or_none()

    latest_disposal = (
        await session.execute(
            select(AssetDisposal)
            .where(
                AssetDisposal.tenant_id == tenant_id,
                AssetDisposal.run_id == run_id,
                AssetDisposal.asset_id == asset_id,
            )
            .order_by(
                desc(AssetDisposal.disposal_date),
                desc(AssetDisposal.created_at),
                desc(AssetDisposal.id),
            )
            .limit(1)
        )
    ).scalar_one_or_none()

    if latest_impairment is None and latest_disposal is None:
        return root_schedule_version_token
    if latest_impairment is not None and latest_disposal is None:
        return latest_impairment.new_schedule_version_token
    if latest_disposal is not None and latest_impairment is None:
        return latest_disposal.new_schedule_version_token

    assert latest_impairment is not None and latest_disposal is not None
    imp_key = (latest_impairment.impairment_date, 1, latest_impairment.created_at, latest_impairment.id)
    disp_key = (latest_disposal.disposal_date, 2, latest_disposal.created_at, latest_disposal.id)
    return (
        latest_impairment.new_schedule_version_token
        if imp_key >= disp_key
        else latest_disposal.new_schedule_version_token
    )


async def get_results(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
) -> dict[str, Any]:
    await _get_run_or_raise(session, tenant_id=tenant_id, run_id=run_id)

    asset_ids = (
        await session.execute(
            select(AssetDepreciationSchedule.asset_id)
            .where(
                AssetDepreciationSchedule.tenant_id == tenant_id,
                AssetDepreciationSchedule.run_id == run_id,
            )
            .distinct()
            .order_by(AssetDepreciationSchedule.asset_id)
        )
    ).scalars().all()

    effective_tokens: dict[UUID, str] = {}
    for asset_id in asset_ids:
        root_token = await _resolve_root_version_token(
            session,
            tenant_id=tenant_id,
            run_id=run_id,
            asset_id=asset_id,
        )
        if root_token is None:
            continue
        effective_tokens[asset_id] = await _resolve_effective_version_token(
            session,
            tenant_id=tenant_id,
            run_id=run_id,
            asset_id=asset_id,
            root_schedule_version_token=root_token,
        )

    rows: list[AssetDepreciationSchedule] = []
    for asset_id, token in effective_tokens.items():
        rows.extend(
            (
                await session.execute(
                    select(AssetDepreciationSchedule)
                    .where(
                        AssetDepreciationSchedule.tenant_id == tenant_id,
                        AssetDepreciationSchedule.run_id == run_id,
                        AssetDepreciationSchedule.asset_id == asset_id,
                        AssetDepreciationSchedule.schedule_version_token == token,
                    )
                    .order_by(
                        AssetDepreciationSchedule.asset_id,
                        AssetDepreciationSchedule.period_seq,
                        AssetDepreciationSchedule.depreciation_date,
                    )
                )
            ).scalars().all()
        )

    rows.sort(key=lambda row: (str(row.asset_id), row.period_seq, row.depreciation_date, str(row.id)))
    payload_rows = [
        {
            "schedule_id": str(row.id),
            "asset_id": str(row.asset_id),
            "period_seq": row.period_seq,
            "depreciation_date": row.depreciation_date,
            "schedule_version_token": row.schedule_version_token,
            "opening_carrying_amount_reporting_currency": _decimal_text(
                row.opening_carrying_amount_reporting_currency
            ),
            "depreciation_amount_reporting_currency": _decimal_text(
                row.depreciation_amount_reporting_currency
            ),
            "closing_carrying_amount_reporting_currency": _decimal_text(
                row.closing_carrying_amount_reporting_currency
            ),
            "fx_rate_used": _decimal_text(row.fx_rate_used),
            "fx_rate_date": row.fx_rate_date,
            "fx_rate_source": row.fx_rate_source,
        }
        for row in rows
    ]

    total = sum((row.depreciation_amount_reporting_currency for row in rows), start=Decimal("0.000000"))
    return {
        "run_id": str(run_id),
        "rows": payload_rows,
        "count": len(payload_rows),
        "total_depreciation_reporting_currency": _decimal_text(total),
    }


async def get_asset_drilldown(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
    asset_id: UUID,
) -> dict[str, Any]:
    return await get_asset_drill(
        session,
        tenant_id=tenant_id,
        run_id=run_id,
        asset_id=asset_id,
    )


async def get_depreciation_drilldown(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
    line_id: UUID,
) -> dict[str, Any]:
    return await get_depreciation_drill(
        session,
        tenant_id=tenant_id,
        run_id=run_id,
        line_id=line_id,
    )


async def get_impairment_drilldown(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
    impairment_id: UUID,
) -> dict[str, Any]:
    return await get_impairment_drill(
        session,
        tenant_id=tenant_id,
        run_id=run_id,
        impairment_id=impairment_id,
    )


async def get_disposal_drilldown(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
    disposal_id: UUID,
) -> dict[str, Any]:
    return await get_disposal_drill(
        session,
        tenant_id=tenant_id,
        run_id=run_id,
        disposal_id=disposal_id,
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
    return await get_depreciation_drilldown(
        session,
        tenant_id=tenant_id,
        run_id=run_id,
        line_id=record_id,
    )


def register_workflow() -> type[Any]:
    from financeops.temporal.fixed_assets_workflows import FixedAssetsWorkflow

    return FixedAssetsWorkflow


class FixedAssetsFacade:
    """Compatibility facade exposing fixed-assets service entrypoints."""

    create_run = staticmethod(create_run)
    mark_run_running = staticmethod(mark_run_running)
    load_assets_for_run = staticmethod(load_assets_for_run)
    generate_depreciation_schedule_for_run = staticmethod(generate_depreciation_schedule_for_run)
    apply_impairment_and_disposal_events_for_run = staticmethod(
        apply_impairment_and_disposal_events_for_run
    )
    build_journal_preview_for_run = staticmethod(build_journal_preview_for_run)
    validate_lineage_for_run = staticmethod(validate_lineage_for_run)
    finalize_run = staticmethod(finalize_run)
    get_run_status = staticmethod(get_run_status)
    get_results = staticmethod(get_results)


__all__ = [
    "MissingLockedRateError",
    "apply_impairment_and_disposal_events_for_run",
    "build_journal_preview_for_run",
    "create_run",
    "finalize_run",
    "generate_depreciation_schedule_for_run",
    "get_asset_drilldown",
    "get_depreciation_drilldown",
    "get_disposal_drilldown",
    "get_drill",
    "get_impairment_drilldown",
    "get_journal_drilldown",
    "get_results",
    "get_run_status",
    "load_assets_for_run",
    "mark_run_running",
    "register_workflow",
    "validate_lineage_for_run",
]

