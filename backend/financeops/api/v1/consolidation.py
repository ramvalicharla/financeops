from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import (
    get_async_session,
    get_current_user,
    require_finance_leader,
    require_finance_team,
)
from financeops.config import settings
from financeops.db.models.users import IamUser
from financeops.schemas.consolidation import (
    ConsolidationAccountDrillResponse,
    ConsolidationEntityDrillResponse,
    ConsolidationLineItemDrillResponse,
    ConsolidationRunAcceptedResponse,
    ConsolidationRunRequest,
    ConsolidationRunStatusResponse,
    ConsolidationResultsResponse,
    ConsolidationSnapshotLineDrillResponse,
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
)
from financeops.temporal.client import get_temporal_client
from financeops.temporal.consolidation_workflows import (
    ConsolidationWorkflow,
    ConsolidationWorkflowInput,
)

router = APIRouter()


@router.post("/run", response_model=ConsolidationRunAcceptedResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_consolidation_run_endpoint(
    body: ConsolidationRunRequest,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> dict:
    correlation_id = str(getattr(request.state, "correlation_id", "") or "")
    run = await create_or_get_run(
        session,
        tenant_id=user.tenant_id,
        initiated_by=user.id,
        period_year=body.period_year,
        period_month=body.period_month,
        parent_currency=body.parent_currency,
        rate_mode=body.rate_mode.value,
        mappings=[
            EntitySnapshotMapping(entity_id=item.entity_id, snapshot_id=item.snapshot_id)
            for item in body.entity_snapshots
        ],
        amount_tolerance_parent=body.amount_tolerance_parent,
        fx_explained_tolerance_parent=body.fx_explained_tolerance_parent,
        timing_tolerance_days=body.timing_tolerance_days,
        correlation_id=correlation_id,
    )
    await session.flush()

    if run.created_new:
        temporal_client = await get_temporal_client()
        await temporal_client.start_workflow(
            ConsolidationWorkflow.run,
            ConsolidationWorkflowInput(
                run_id=str(run.run_id),
                tenant_id=str(user.tenant_id),
                correlation_id=correlation_id,
                requested_by=str(user.id),
                config_hash=run.request_signature,
            ),
            id=run.workflow_id,
            task_queue=settings.TEMPORAL_TASK_QUEUE,
            execution_timeout=timedelta(minutes=15),
        )

    return {
        "run_id": str(run.run_id),
        "workflow_id": run.workflow_id,
        "status": "accepted" if run.created_new else run.status,
        "correlation_id": correlation_id,
    }


@router.get("/run/{run_id}", response_model=ConsolidationRunStatusResponse)
async def get_consolidation_run_status_endpoint(
    run_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    return await get_run_status(
        session,
        tenant_id=user.tenant_id,
        run_id=run_id,
    )


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
