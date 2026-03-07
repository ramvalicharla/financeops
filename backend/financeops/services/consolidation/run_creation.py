from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.consolidation import ConsolidationRun
from financeops.services.audit_writer import AuditEvent, AuditWriter
from financeops.services.consolidation.entity_loader import (
    EntitySnapshotMapping,
    load_entity_snapshots,
)
from financeops.services.consolidation.fx_application import ensure_locked_rates_available
from financeops.services.consolidation.run_events import append_run_event, get_latest_run_event
from financeops.services.consolidation.service_types import (
    RunCreateResult,
    build_request_signature,
    request_signature_payload,
    resolved_tolerance,
)
from financeops.services.fx.normalization import normalize_currency_code


async def create_or_get_run(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    initiated_by: UUID,
    period_year: int,
    period_month: int,
    parent_currency: str,
    rate_mode: str,
    mappings: list[EntitySnapshotMapping],
    amount_tolerance_parent: Decimal | None,
    fx_explained_tolerance_parent: Decimal | None,
    timing_tolerance_days: int | None,
    correlation_id: str | None,
) -> RunCreateResult:
    parent = normalize_currency_code(parent_currency)
    bundles = await load_entity_snapshots(
        session,
        tenant_id=tenant_id,
        period_year=period_year,
        period_month=period_month,
        mappings=mappings,
    )
    if rate_mode == "month_end_locked":
        entity_currencies = {bundle.header.entity_currency for bundle in bundles}
        await ensure_locked_rates_available(
            session,
            tenant_id=tenant_id,
            period_year=period_year,
            period_month=period_month,
            entity_currencies=entity_currencies,
            parent_currency=parent,
        )
    tolerance_payload = resolved_tolerance(
        amount_tolerance_parent=amount_tolerance_parent,
        fx_explained_tolerance_parent=fx_explained_tolerance_parent,
        timing_tolerance_days=timing_tolerance_days,
    )
    config_payload = request_signature_payload(
        period_year=period_year,
        period_month=period_month,
        parent_currency=parent,
        rate_mode=rate_mode,
        mappings=mappings,
        tolerance_payload=tolerance_payload,
    )
    signature = build_request_signature(config_payload)
    existing_result = await session.execute(
        select(ConsolidationRun).where(
            ConsolidationRun.tenant_id == tenant_id,
            ConsolidationRun.request_signature == signature,
        )
    )
    existing = existing_result.scalar_one_or_none()
    if existing is not None:
        latest = await get_latest_run_event(session, tenant_id=tenant_id, run_id=existing.id)
        return RunCreateResult(
            run_id=existing.id,
            workflow_id=existing.workflow_id,
            request_signature=existing.request_signature,
            status=latest.event_type,
            created_new=False,
        )

    workflow_id = f"consolidation-{signature[:24]}"
    run = await AuditWriter.insert_financial_record(
        session,
        model_class=ConsolidationRun,
        tenant_id=tenant_id,
        record_data={
            "period_year": period_year,
            "period_month": period_month,
            "parent_currency": parent,
            "request_signature": signature,
            "workflow_id": workflow_id,
            "correlation_id": correlation_id,
        },
        values={
            "period_year": period_year,
            "period_month": period_month,
            "parent_currency": parent,
            "initiated_by": initiated_by,
            "request_signature": signature,
            "configuration_json": config_payload,
            "workflow_id": workflow_id,
            "correlation_id": correlation_id,
        },
        audit=AuditEvent(
            tenant_id=tenant_id,
            user_id=initiated_by,
            action="consolidation.run.created",
            resource_type="consolidation_run",
            new_value={
                "period_year": period_year,
                "period_month": period_month,
                "parent_currency": parent,
                "request_signature": signature,
                "correlation_id": correlation_id,
            },
        ),
    )
    await append_run_event(
        session,
        tenant_id=tenant_id,
        run_id=run.id,
        user_id=initiated_by,
        event_type="accepted",
        idempotency_key="run-created",
        metadata_json={"workflow_id": workflow_id},
        correlation_id=correlation_id,
    )
    return RunCreateResult(
        run_id=run.id,
        workflow_id=workflow_id,
        request_signature=signature,
        status="accepted",
        created_new=True,
    )
