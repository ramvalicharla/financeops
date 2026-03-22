from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, require_finance_leader, require_finance_team
from financeops.config import settings
from financeops.db.models.users import IamUser
from financeops.platform.services.enforcement.interceptors import require_valid_context_token
from financeops.schemas.fixed_assets import (
    FarDepreciationDrillResponse,
    FarDisposalDrillResponse,
    FarImpairmentDrillResponse,
    FarJournalDrillResponse,
    FarResultsResponse,
    FarRunAcceptedResponse,
    FarRunRequest,
    FarRunStatusResponse,
    FixedAssetDrillResponse,
)
from financeops.services.fixed_assets import (
    create_run,
    get_asset_drilldown,
    get_depreciation_drilldown,
    get_disposal_drilldown,
    get_impairment_drilldown,
    get_journal_drilldown,
    get_results,
    get_run_status,
)
from financeops.temporal.client import get_temporal_client
from financeops.temporal.fixed_assets_workflows import (
    FixedAssetsWorkflow,
    FixedAssetsWorkflowInput,
)

router = APIRouter(dependencies=[Depends(require_valid_context_token(module_code="fixed_assets"))])


@router.post("/run", response_model=FarRunAcceptedResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_fixed_assets_run_endpoint(
    body: FarRunRequest,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> dict:
    correlation_id = str(getattr(request.state, "correlation_id", "") or "")
    run = await create_run(
        session,
        tenant_id=user.tenant_id,
        initiated_by=user.id,
        request_payload=body.model_dump(mode="json"),
        correlation_id=correlation_id,
    )
    await session.flush()

    if run["created_new"]:
        temporal_client = await get_temporal_client()
        await temporal_client.start_workflow(
            FixedAssetsWorkflow.run,
            FixedAssetsWorkflowInput(
                run_id=str(run["run_id"]),
                tenant_id=str(user.tenant_id),
                correlation_id=correlation_id,
                requested_by=str(user.id),
                config_hash=str(run["request_signature"]),
            ),
            id=str(run["workflow_id"]),
            task_queue=settings.TEMPORAL_TASK_QUEUE,
            execution_timeout=timedelta(minutes=20),
        )

    return {
        "run_id": str(run["run_id"]),
        "workflow_id": str(run["workflow_id"]),
        "status": "accepted" if run["created_new"] else str(run["status"]),
        "correlation_id": correlation_id,
    }


@router.get("/run/{run_id}", response_model=FarRunStatusResponse)
async def get_fixed_assets_run_status_endpoint(
    run_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict:
    return await get_run_status(
        session,
        tenant_id=user.tenant_id,
        run_id=run_id,
    )


@router.get("/results/{run_id}", response_model=FarResultsResponse)
async def get_fixed_assets_results_endpoint(
    run_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict:
    return await get_results(
        session,
        tenant_id=user.tenant_id,
        run_id=run_id,
    )


@router.get("/run/{run_id}/assets/{asset_id}", response_model=FixedAssetDrillResponse)
async def get_fixed_asset_drill_endpoint(
    run_id: UUID,
    asset_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict:
    return await get_asset_drilldown(
        session,
        tenant_id=user.tenant_id,
        run_id=run_id,
        asset_id=asset_id,
    )


@router.get("/run/{run_id}/depreciation-lines/{line_id}", response_model=FarDepreciationDrillResponse)
async def get_fixed_asset_depreciation_drill_endpoint(
    run_id: UUID,
    line_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict:
    return await get_depreciation_drilldown(
        session,
        tenant_id=user.tenant_id,
        run_id=run_id,
        line_id=line_id,
    )


@router.get("/run/{run_id}/impairments/{impairment_id}", response_model=FarImpairmentDrillResponse)
async def get_fixed_asset_impairment_drill_endpoint(
    run_id: UUID,
    impairment_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict:
    return await get_impairment_drilldown(
        session,
        tenant_id=user.tenant_id,
        run_id=run_id,
        impairment_id=impairment_id,
    )


@router.get("/run/{run_id}/disposals/{disposal_id}", response_model=FarDisposalDrillResponse)
async def get_fixed_asset_disposal_drill_endpoint(
    run_id: UUID,
    disposal_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict:
    return await get_disposal_drilldown(
        session,
        tenant_id=user.tenant_id,
        run_id=run_id,
        disposal_id=disposal_id,
    )


@router.get("/run/{run_id}/journal-entries/{journal_id}", response_model=FarJournalDrillResponse)
async def get_fixed_asset_journal_drill_endpoint(
    run_id: UUID,
    journal_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict:
    return await get_journal_drilldown(
        session,
        tenant_id=user.tenant_id,
        run_id=run_id,
        journal_id=journal_id,
    )
