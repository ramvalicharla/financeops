from __future__ import annotations

import asyncio
from datetime import date, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import (
    get_async_session,
    require_finance_leader,
    require_finance_team,
)
from financeops.config import settings
from financeops.core.exceptions import ValidationError
from financeops.core.governance.events import GovernanceActor, emit_governance_event
from financeops.core.intent.api import build_idempotency_key, build_intent_actor
from financeops.core.intent.enums import IntentType
from financeops.core.intent.service import IntentService
from financeops.db.models.users import IamUser
from financeops.modules.closing_checklist.service import run_auto_complete_for_event
from financeops.schemas.consolidation import (
    ConsolidationAccountDrillResponse,
    ConsolidationEntityDrillResponse,
    ConsolidationGroupRunRequest,
    ConsolidationGroupRunResponse,
    ConsolidationGroupRunStatementsResponse,
    ConsolidationGroupSummaryResponse,
    ConsolidationLineItemDrillResponse,
    ConsolidationRunAcceptedResponse,
    ConsolidationRunRequest,
    ConsolidationRunStatusResponse,
    ConsolidationResultsResponse,
    ConsolidationSnapshotLineDrillResponse,
    ConsolidationTranslationResponse,
    IntercompanyDifferencesResponse,
)
from financeops.services.consolidation import (
    EntitySnapshotMapping,
    build_export,
    create_or_get_run,
    get_account_drilldown,
    get_entity_drilldown,
    get_line_item_drilldown,
    get_run_status,
    get_snapshot_line_drilldown,
    list_ic_differences,
    list_results,
    translate_group_financials,
)
from financeops.services.consolidation.group_consolidation_service import (
    get_group_consolidation_run,
    get_group_consolidation_run_statements,
    get_group_consolidation_summary,
    run_group_consolidation,
)
from financeops.observability.workflow_signals import (
    complete_workflow,
    fail_workflow,
    start_workflow,
)
from financeops.modules.accounting_layer.application.governance_service import (
    assert_group_period_not_hard_closed,
    resolve_effective_period_lock,
)

router = APIRouter()


@router.post("/run", response_model=ConsolidationRunAcceptedResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_consolidation_run_endpoint(
    body: ConsolidationRunRequest | ConsolidationGroupRunRequest,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> dict:
    correlation_id = str(getattr(request.state, "correlation_id", "") or "")
    timer = start_workflow(
        workflow="consolidation_run",
        tenant_id=str(user.tenant_id),
        module="consolidation",
        correlation_id=correlation_id,
    )
    try:
        if isinstance(body, ConsolidationGroupRunRequest):
            await assert_group_period_not_hard_closed(
                session,
                tenant_id=user.tenant_id,
                org_group_id=body.org_group_id,
                as_of_date=body.as_of_date,
            )
            payload = await run_group_consolidation(
                session,
                tenant_id=user.tenant_id,
                initiated_by=user.id,
                org_group_id=body.org_group_id,
                as_of_date=body.as_of_date,
                from_date=body.from_date,
                to_date=body.to_date,
                presentation_currency=body.presentation_currency,
                correlation_id=correlation_id,
            )
            complete_workflow(
                timer,
                status="accepted",
                extra={"run_id": payload.get("run_id"), "workflow_id": payload.get("workflow_id")},
            )
            return payload

        period_lock = await resolve_effective_period_lock(
            session,
            tenant_id=user.tenant_id,
            org_entity_id=None,
            fiscal_year=body.period_year,
            period_number=body.period_month,
        )
        if period_lock.is_hard_closed:
            raise ValidationError("Period is HARD_CLOSED. Consolidation rerun is blocked.")

        governed = await IntentService(session).submit_intent(
            intent_type=IntentType.START_LEGACY_CONSOLIDATION_RUN,
            actor=build_intent_actor(request, user),
            payload={
                "period_year": body.period_year,
                "period_month": body.period_month,
                "parent_currency": body.parent_currency,
                "rate_mode": body.rate_mode.value,
                "entity_snapshots": [
                    {"entity_id": str(item.entity_id), "snapshot_id": str(item.snapshot_id)}
                    for item in body.entity_snapshots
                ],
                "amount_tolerance_parent": (
                    str(body.amount_tolerance_parent) if body.amount_tolerance_parent is not None else None
                ),
                "fx_explained_tolerance_parent": (
                    str(body.fx_explained_tolerance_parent)
                    if body.fx_explained_tolerance_parent is not None
                    else None
                ),
                "timing_tolerance_days": body.timing_tolerance_days,
                "correlation_id": correlation_id,
            },
            idempotency_key=build_idempotency_key(
                request,
                intent_type=IntentType.START_LEGACY_CONSOLIDATION_RUN,
                actor=user,
                body={
                    "period_year": body.period_year,
                    "period_month": body.period_month,
                    "parent_currency": body.parent_currency,
                    "rate_mode": body.rate_mode.value,
                    "entity_snapshots": [
                        {"entity_id": str(item.entity_id), "snapshot_id": str(item.snapshot_id)}
                        for item in body.entity_snapshots
                    ],
                    "amount_tolerance_parent": (
                        str(body.amount_tolerance_parent) if body.amount_tolerance_parent is not None else None
                    ),
                    "fx_explained_tolerance_parent": (
                        str(body.fx_explained_tolerance_parent)
                        if body.fx_explained_tolerance_parent is not None
                        else None
                    ),
                    "timing_tolerance_days": body.timing_tolerance_days,
                    "correlation_id": correlation_id,
                },
            ),
        )
        payload = dict(governed.record_refs or {})
        complete_workflow(timer, status="accepted", extra={"run_id": payload["run_id"]})
        return payload
    except Exception as exc:
        fail_workflow(timer, error=exc)
        raise


@router.get("/summary", response_model=ConsolidationGroupSummaryResponse)
async def get_consolidation_summary_endpoint(
    org_group_id: UUID = Query(...),
    as_of_date: date = Query(...),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    presentation_currency: str | None = Query(default=None, min_length=3, max_length=3),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict:
    return await get_group_consolidation_summary(
        session,
        tenant_id=user.tenant_id,
        org_group_id=org_group_id,
        as_of_date=as_of_date,
        from_date=from_date,
        to_date=to_date,
        presentation_currency=presentation_currency,
    )


@router.get("/runs/{run_id}", response_model=ConsolidationGroupRunResponse)
async def get_group_consolidation_run_endpoint(
    run_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict:
    return await get_group_consolidation_run(
        session,
        tenant_id=user.tenant_id,
        run_id=run_id,
    )


@router.get(
    "/runs/{run_id}/statements",
    response_model=ConsolidationGroupRunStatementsResponse,
)
async def get_group_consolidation_run_statements_endpoint(
    run_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict:
    return await get_group_consolidation_run_statements(
        session,
        tenant_id=user.tenant_id,
        run_id=run_id,
    )


@router.get("/translate", response_model=ConsolidationTranslationResponse)
async def get_consolidation_translation_endpoint(
    request: Request,
    org_group_id: UUID = Query(...),
    presentation_currency: str = Query(..., min_length=3, max_length=3),
    as_of_date: date = Query(...),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict:
    correlation_id = str(getattr(request.state, "correlation_id", "") or "")
    timer = start_workflow(
        workflow="translation_run",
        tenant_id=str(user.tenant_id),
        module="consolidation",
        correlation_id=correlation_id or None,
    )
    await assert_group_period_not_hard_closed(
        session,
        tenant_id=user.tenant_id,
        org_group_id=org_group_id,
        as_of_date=as_of_date,
    )
    try:
        payload = await translate_group_financials(
            session,
            tenant_id=user.tenant_id,
            org_group_id=org_group_id,
            presentation_currency=presentation_currency,
            as_of_date=as_of_date,
            initiated_by=user.id,
        )
        await emit_governance_event(
            session,
            tenant_id=user.tenant_id,
            module_key="period_close",
            subject_type="consolidation_translation",
            subject_id=str(payload.get("translation_run_id") or org_group_id),
            event_type="CONSOLIDATION_TRANSLATE",
            actor=GovernanceActor(user_id=user.id, role=user.role.value),
            entity_id=None,
            payload={
                "org_group_id": str(org_group_id),
                "as_of_date": as_of_date.isoformat(),
                "presentation_currency": presentation_currency,
            },
        )
        complete_workflow(
            timer,
            status="success",
            extra={"run_id": str(payload.get("translation_run_id") or "")},
        )
        return payload
    except Exception as exc:
        fail_workflow(timer, error=exc)
        raise


@router.get("/run/{run_id}", response_model=ConsolidationRunStatusResponse)
async def get_consolidation_run_status_endpoint(
    run_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict:
    payload = await get_run_status(
        session,
        tenant_id=user.tenant_id,
        run_id=run_id,
    )
    status_text = str(payload.get("status") or "").lower()
    if status_text in {"completed", "complete"}:
        year = payload.get("period_year")
        month = payload.get("period_month")
        if isinstance(year, int) and isinstance(month, int):
            period = f"{year:04d}-{month:02d}"
        else:
            period = payload.get("period") or payload.get("reporting_period") or ""
            period = str(period)[:7] if str(period) else ""
        if period:
            asyncio.create_task(
                run_auto_complete_for_event(
                    tenant_id=user.tenant_id,
                    period=period,
                    event="consolidation_complete",
                )
            )
    return payload


@router.get("/results/{run_id}", response_model=ConsolidationResultsResponse)
async def get_consolidation_results_endpoint(
    run_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict:
    return await list_results(
        session,
        tenant_id=user.tenant_id,
        run_id=run_id,
    )


@router.get("/ic-differences/{run_id}", response_model=IntercompanyDifferencesResponse)
async def get_consolidation_ic_differences_endpoint(
    run_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict:
    return await list_ic_differences(
        session,
        tenant_id=user.tenant_id,
        run_id=run_id,
    )


@router.get("/export/{run_id}")
async def get_consolidation_export_endpoint(
    run_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> Response:
    export_payload = await build_export(
        session,
        tenant_id=user.tenant_id,
        run_id=run_id,
    )
    headers = {
        "Content-Disposition": f'attachment; filename="consolidation_{run_id}.xlsx"',
        "X-Export-Checksum": export_payload.checksum,
    }
    return Response(
        content=export_payload.workbook_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )


@router.get(
    "/run/{run_id}/accounts/{account_code}",
    response_model=ConsolidationAccountDrillResponse,
)
async def get_consolidation_account_drilldown_endpoint(
    run_id: UUID,
    account_code: str,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict:
    return await get_account_drilldown(
        session,
        tenant_id=user.tenant_id,
        run_id=run_id,
        account_code=account_code,
    )


@router.get(
    "/run/{run_id}/entities/{entity_id}",
    response_model=ConsolidationEntityDrillResponse,
)
async def get_consolidation_entity_drilldown_endpoint(
    run_id: UUID,
    entity_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict:
    return await get_entity_drilldown(
        session,
        tenant_id=user.tenant_id,
        run_id=run_id,
        entity_id=entity_id,
    )


@router.get(
    "/run/{run_id}/line-items/{line_item_id}",
    response_model=ConsolidationLineItemDrillResponse,
)
async def get_consolidation_line_item_drilldown_endpoint(
    run_id: UUID,
    line_item_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict:
    return await get_line_item_drilldown(
        session,
        tenant_id=user.tenant_id,
        run_id=run_id,
        line_item_id=line_item_id,
    )


@router.get(
    "/run/{run_id}/snapshot-lines/{snapshot_line_id}",
    response_model=ConsolidationSnapshotLineDrillResponse,
)
async def get_consolidation_snapshot_line_drilldown_endpoint(
    run_id: UUID,
    snapshot_line_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict:
    return await get_snapshot_line_drilldown(
        session,
        tenant_id=user.tenant_id,
        run_id=run_id,
        snapshot_line_id=snapshot_line_id,
    )
