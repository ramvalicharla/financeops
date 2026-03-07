from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import require_finance_leader, require_finance_team, get_async_session
from financeops.config import settings
from financeops.db.models.users import IamUser
from financeops.schemas.revenue import (
    RevenueContractDrillResponse,
    RevenueJournalDrillResponse,
    RevenueObligationDrillResponse,
    RevenueResultsResponse,
    RevenueRunAcceptedResponse,
    RevenueRunRequest,
    RevenueRunStatusResponse,
    RevenueScheduleDrillResponse,
)
from financeops.services.revenue import (
    create_run,
    get_contract_drilldown,
    get_journal_drilldown,
    get_obligation_drilldown,
    get_results,
    get_run_status,
    get_schedule_drilldown,
)
from financeops.temporal.client import get_temporal_client
from financeops.temporal.revenue_workflows import (
    RevenueRecognitionWorkflow,
    RevenueRecognitionWorkflowInput,
)

router = APIRouter()


@router.post("/run", response_model=RevenueRunAcceptedResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_revenue_run_endpoint(
    body: RevenueRunRequest,
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
    await session.commit()

    if run["created_new"]:
        temporal_client = await get_temporal_client()
        await temporal_client.start_workflow(
            RevenueRecognitionWorkflow.run,
            RevenueRecognitionWorkflowInput(
                run_id=str(run["run_id"]),
                tenant_id=str(user.tenant_id),
                correlation_id=correlation_id,
                requested_by=str(user.id),
                config_hash=str(run["request_signature"]),
            ),
            id=str(run["workflow_id"]),
            task_queue=settings.TEMPORAL_TASK_QUEUE,
            execution_timeout=timedelta(minutes=15),
        )

    return {
        "run_id": str(run["run_id"]),
        "workflow_id": str(run["workflow_id"]),
        "status": "accepted" if run["created_new"] else str(run["status"]),
        "correlation_id": correlation_id,
    }


@router.get("/run/{run_id}", response_model=RevenueRunStatusResponse)
async def get_revenue_run_status_endpoint(
    run_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict:
    return await get_run_status(
        session,
        tenant_id=user.tenant_id,
        run_id=run_id,
    )


@router.get("/results/{run_id}", response_model=RevenueResultsResponse)
async def get_revenue_results_endpoint(
    run_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict:
    return await get_results(
        session,
        tenant_id=user.tenant_id,
        run_id=run_id,
    )


@router.get("/run/{run_id}/contracts/{contract_id}", response_model=RevenueContractDrillResponse)
async def get_revenue_contract_drill_endpoint(
    run_id: UUID,
    contract_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict:
    return await get_contract_drilldown(
        session,
        tenant_id=user.tenant_id,
        run_id=run_id,
        contract_id=contract_id,
    )


@router.get("/run/{run_id}/obligations/{obligation_id}", response_model=RevenueObligationDrillResponse)
async def get_revenue_obligation_drill_endpoint(
    run_id: UUID,
    obligation_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict:
    return await get_obligation_drilldown(
        session,
        tenant_id=user.tenant_id,
        run_id=run_id,
        obligation_id=obligation_id,
    )


@router.get("/run/{run_id}/schedule-lines/{schedule_id}", response_model=RevenueScheduleDrillResponse)
async def get_revenue_schedule_drill_endpoint(
    run_id: UUID,
    schedule_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict:
    return await get_schedule_drilldown(
        session,
        tenant_id=user.tenant_id,
        run_id=run_id,
        schedule_id=schedule_id,
    )


@router.get("/run/{run_id}/journal-entries/{journal_id}", response_model=RevenueJournalDrillResponse)
async def get_revenue_journal_drill_endpoint(
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
