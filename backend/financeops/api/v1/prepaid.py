from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, require_finance_leader, require_finance_team
from financeops.db.models.prepaid import PrepaidAmortizationSchedule, PrepaidRun
from financeops.core.intent.api import build_idempotency_key, build_intent_actor
from financeops.core.intent.enums import IntentType
from financeops.core.intent.service import IntentService
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
    get_journal_drilldown,
    get_prepaid_drilldown,
    get_results,
    get_run_status,
    get_schedule_drilldown,
)

router = APIRouter(
    dependencies=[Depends(validate_optional_control_plane_token(module_code="prepaid"))]
)


async def _submit_intent(
    request: Request,
    session: AsyncSession,
    *,
    user: IamUser,
    intent_type: IntentType,
    payload: dict,
):
    service = IntentService(session)
    return await service.submit_intent(
        intent_type=intent_type,
        actor=build_intent_actor(request, user),
        payload=payload,
        idempotency_key=build_idempotency_key(
            request,
            intent_type=intent_type,
            actor=user,
            body=payload,
        ),
    )


@router.get("/schedule")
async def get_prepaid_schedule_endpoint(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> list[dict]:
    latest_run = (
        await session.execute(
            select(PrepaidRun)
            .where(PrepaidRun.tenant_id == user.tenant_id)
            .order_by(PrepaidRun.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if latest_run is None:
        return []
    rows = (
        await session.execute(
            select(PrepaidAmortizationSchedule)
            .where(
                PrepaidAmortizationSchedule.tenant_id == user.tenant_id,
                PrepaidAmortizationSchedule.run_id == latest_run.id,
            )
            .order_by(
                PrepaidAmortizationSchedule.amortization_date.asc(),
                PrepaidAmortizationSchedule.period_seq.asc(),
            )
        )
    ).scalars().all()
    return [
        {
            "id": str(row.id),
            "run_id": str(row.run_id),
            "prepaid_id": str(row.prepaid_id),
            "period_seq": row.period_seq,
            "amortization_date": row.amortization_date.isoformat(),
            "recognition_period_year": row.recognition_period_year,
            "recognition_period_month": row.recognition_period_month,
            "base_amount_contract_currency": str(row.base_amount_contract_currency),
            "amortized_amount_reporting_currency": str(row.amortized_amount_reporting_currency),
            "cumulative_amortized_reporting_currency": str(row.cumulative_amortized_reporting_currency),
            "fx_rate_used": str(row.fx_rate_used),
            "schedule_status": row.schedule_status,
        }
        for row in rows
    ]


@router.post("/run", response_model=PrepaidRunAcceptedResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_prepaid_run_endpoint(
    body: PrepaidRunRequest,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> dict:
    correlation_id = str(getattr(request.state, "correlation_id", "") or "")
    result = await _submit_intent(
        request,
        session,
        user=user,
        intent_type=IntentType.RUN_PREPAID_WORKFLOW,
        payload={
            "request_payload": body.model_dump(mode="json"),
            "period_year": body.period_year,
            "period_number": body.period_month,
            "correlation_id": correlation_id,
        },
    )
    record_refs = result.record_refs or {}
    return {
        "run_id": str(record_refs["run_id"]),
        "workflow_id": str(record_refs["workflow_id"]),
        "status": str(record_refs.get("status") or "accepted"),
        "correlation_id": correlation_id,
        "intent_id": str(result.intent_id),
        "job_id": str(result.job_id) if result.job_id else None,
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
