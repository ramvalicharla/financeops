from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, require_finance_leader, require_finance_team
from financeops.core.intent.api import build_idempotency_key, build_intent_actor
from financeops.core.intent.enums import IntentType
from financeops.core.intent.service import IntentService
from financeops.db.models.users import IamUser
from financeops.platform.services.enforcement.interceptors import (
    validate_optional_control_plane_token,
)
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
    get_asset_drilldown,
    get_depreciation_drilldown,
    get_disposal_drilldown,
    get_impairment_drilldown,
    get_journal_drilldown,
    get_results,
    get_run_status,
)

router = APIRouter(
    dependencies=[Depends(validate_optional_control_plane_token(module_code="fixed_assets"))]
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


@router.post("/run", response_model=FarRunAcceptedResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_fixed_assets_run_endpoint(
    body: FarRunRequest,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> dict:
    correlation_id = str(getattr(request.state, "correlation_id", "") or "")
    result = await _submit_intent(
        request,
        session,
        user=user,
        intent_type=IntentType.RUN_FIXED_ASSET_WORKFLOW,
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
