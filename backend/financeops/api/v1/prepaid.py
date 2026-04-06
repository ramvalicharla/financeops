from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, require_finance_leader, require_finance_team
from financeops.config import settings
from financeops.db.models.users import IamUser
from financeops.platform.services.enforcement.interceptors import (
    validate_optional_control_plane_token,
)
from financeops.schemas.prepaid import (
    PrepaidJournalDrillResponse,
    PrepaidRegistryDrillResponse,
    PrepaidResultsResponse,
    PrepaidRunAcceptedResponse,
    PrepaidRunRequest,
    PrepaidRunStatusResponse,
    PrepaidScheduleDrillResponse,
)
from financeops.services.prepaid import (
    create_run,
    get_journal_drilldown,
    get_prepaid_drilldown,
    get_results,
    get_run_status,
    get_schedule_drilldown,
)
from financeops.temporal.client import get_temporal_client
from financeops.temporal.prepaid_workflows import (
    PrepaidAmortizationWorkflow,
    PrepaidAmortizationWorkflowInput,
)

router = APIRouter(
    dependencies=[Depends(validate_optional_control_plane_token(module_code="prepaid"))]
)


@router.post("/run", response_model=PrepaidRunAcceptedResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_prepaid_run_endpoint(
    body: PrepaidRunRequest,
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
            PrepaidAmortizationWorkflow.run,
            PrepaidAmortizationWorkflowInput(
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


@router.get("/run/{run_id}", response_model=PrepaidRunStatusResponse)
async def get_prepaid_run_status_endpoint(
    run_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict:
    return await get_run_status(
        session,
        tenant_id=user.tenant_id,
        run_id=run_id,
    )


@router.get("/results/{run_id}", response_model=PrepaidResultsResponse)
async def get_prepaid_results_endpoint(
    run_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict:
    return await get_results(
        session,
        tenant_id=user.tenant_id,
        run_id=run_id,
    )


@router.get("/run/{run_id}/prepaids/{prepaid_id}", response_model=PrepaidRegistryDrillResponse)
async def get_prepaid_registry_drill_endpoint(
    run_id: UUID,
    prepaid_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict:
    return await get_prepaid_drilldown(
        session,
        tenant_id=user.tenant_id,
        run_id=run_id,
        prepaid_id=prepaid_id,
    )


@router.get("/run/{run_id}/schedule-lines/{schedule_id}", response_model=PrepaidScheduleDrillResponse)
async def get_prepaid_schedule_drill_endpoint(
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


@router.get("/run/{run_id}/journal-entries/{journal_id}", response_model=PrepaidJournalDrillResponse)
async def get_prepaid_journal_drill_endpoint(
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
