from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, require_finance_leader, require_finance_team
from financeops.config import settings
from financeops.core.intent.dispatcher import JobDispatcher
from financeops.db.models.lease import LeaseLiabilitySchedule, LeaseRun
from financeops.db.models.users import IamUser
from financeops.schemas.lease import (
    LeaseContractDrillResponse,
    LeaseJournalDrillResponse,
    LeaseLiabilityDrillResponse,
    LeasePaymentDrillResponse,
    LeaseResultsResponse,
    LeaseRouDrillResponse,
    LeaseRunAcceptedResponse,
    LeaseRunRequest,
    LeaseRunStatusResponse,
)
from financeops.services.lease import (
    create_run,
    get_journal_drilldown,
    get_lease_drilldown,
    get_liability_drilldown,
    get_payment_drilldown,
    get_results,
    get_rou_drilldown,
    get_run_status,
)
from financeops.temporal.lease_workflows import (
    LeaseAccountingWorkflow,
    LeaseAccountingWorkflowInput,
)

router = APIRouter()


@router.get("/schedule")
async def get_lease_schedule_endpoint(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> list[dict]:
    latest_run = (
        await session.execute(
            select(LeaseRun)
            .where(LeaseRun.tenant_id == user.tenant_id)
            .order_by(LeaseRun.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if latest_run is None:
        return []
    rows = (
        await session.execute(
            select(LeaseLiabilitySchedule)
            .where(
                LeaseLiabilitySchedule.tenant_id == user.tenant_id,
                LeaseLiabilitySchedule.run_id == latest_run.id,
            )
            .order_by(LeaseLiabilitySchedule.schedule_date.asc(), LeaseLiabilitySchedule.period_seq.asc())
        )
    ).scalars().all()
    return [
        {
            "id": str(row.id),
            "run_id": str(row.run_id),
            "lease_id": str(row.lease_id),
            "period_seq": row.period_seq,
            "schedule_date": row.schedule_date.isoformat(),
            "period_year": row.period_year,
            "period_month": row.period_month,
            "opening_liability": str(row.opening_liability_reporting_currency),
            "interest_expense": str(row.interest_expense_reporting_currency),
            "payment_amount": str(row.payment_amount_reporting_currency),
            "closing_liability": str(row.closing_liability_reporting_currency),
            "fx_rate_used": str(row.fx_rate_used),
        }
        for row in rows
    ]


@router.post("/run", response_model=LeaseRunAcceptedResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_lease_run_endpoint(
    body: LeaseRunRequest,
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
        await JobDispatcher().start_temporal_workflow(
            LeaseAccountingWorkflow.run,
            LeaseAccountingWorkflowInput(
                run_id=str(run["run_id"]),
                tenant_id=str(user.tenant_id),
                correlation_id=correlation_id,
                requested_by=str(user.id),
                config_hash=str(run["request_signature"]),
            ),
            workflow_id=str(run["workflow_id"]),
            task_queue=settings.TEMPORAL_TASK_QUEUE,
            execution_timeout=timedelta(minutes=15),
        )

    return {
        "run_id": str(run["run_id"]),
        "workflow_id": str(run["workflow_id"]),
        "status": "accepted" if run["created_new"] else str(run["status"]),
        "correlation_id": correlation_id,
    }


@router.get("/run/{run_id}", response_model=LeaseRunStatusResponse)
async def get_lease_run_status_endpoint(
    run_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict:
    return await get_run_status(
        session,
        tenant_id=user.tenant_id,
        run_id=run_id,
    )


@router.get("/results/{run_id}", response_model=LeaseResultsResponse)
async def get_lease_results_endpoint(
    run_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict:
    return await get_results(
        session,
        tenant_id=user.tenant_id,
        run_id=run_id,
    )


@router.get("/run/{run_id}/leases/{lease_id}", response_model=LeaseContractDrillResponse)
async def get_lease_contract_drill_endpoint(
    run_id: UUID,
    lease_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict:
    return await get_lease_drilldown(
        session,
        tenant_id=user.tenant_id,
        run_id=run_id,
        lease_id=lease_id,
    )


@router.get("/run/{run_id}/payments/{payment_id}", response_model=LeasePaymentDrillResponse)
async def get_lease_payment_drill_endpoint(
    run_id: UUID,
    payment_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict:
    return await get_payment_drilldown(
        session,
        tenant_id=user.tenant_id,
        run_id=run_id,
        payment_id=payment_id,
    )


@router.get("/run/{run_id}/liability-lines/{line_id}", response_model=LeaseLiabilityDrillResponse)
async def get_lease_liability_drill_endpoint(
    run_id: UUID,
    line_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict:
    return await get_liability_drilldown(
        session,
        tenant_id=user.tenant_id,
        run_id=run_id,
        line_id=line_id,
    )


@router.get("/run/{run_id}/rou-lines/{line_id}", response_model=LeaseRouDrillResponse)
async def get_lease_rou_drill_endpoint(
    run_id: UUID,
    line_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict:
    return await get_rou_drilldown(
        session,
        tenant_id=user.tenant_id,
        run_id=run_id,
        line_id=line_id,
    )


@router.get("/run/{run_id}/journal-entries/{journal_id}", response_model=LeaseJournalDrillResponse)
async def get_lease_journal_drill_endpoint(
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
