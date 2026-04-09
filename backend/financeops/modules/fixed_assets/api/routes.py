from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user
from financeops.core.intent.api import build_idempotency_key, build_intent_actor
from financeops.core.intent.enums import IntentType
from financeops.core.intent.service import IntentService
from financeops.db.models.users import IamUser
from financeops.modules.fixed_assets.models import FaAssetClass, FaDepreciationRun, FaImpairment, FaRevaluation
from financeops.modules.fixed_assets.api.schemas import (
    FaAssetClassCreateRequest,
    FaAssetClassResponse,
    FaAssetClassUpdateRequest,
    FaAssetCreateRequest,
    FaAssetResponse,
    FaAssetUpdateRequest,
    FaDepreciationRunRequest,
    FaDepreciationRunResponse,
    FaDisposalRequest,
    FaImpairmentRequest,
    FaImpairmentResponse,
    FaPeriodDepreciationRequest,
    FaRegisterLineResponse,
    FaRevaluationRequest,
    FaRevaluationResponse,
)
from financeops.modules.fixed_assets.application.fixed_asset_service import FixedAssetService
from financeops.platform.services.tenancy.entity_access import assert_entity_access
from financeops.shared_kernel.pagination import Paginated

router = APIRouter(prefix="/fixed-assets", tags=["fixed-assets"])


async def _submit_intent(
    request: Request,
    session: AsyncSession,
    *,
    user: IamUser,
    intent_type: IntentType,
    payload: dict[str, Any],
    target_id: uuid.UUID | None = None,
):
    service = IntentService(session)
    return await service.submit_intent(
        intent_type=intent_type,
        actor=build_intent_actor(request, user),
        payload=payload,
        target_id=target_id,
        idempotency_key=build_idempotency_key(
            request,
            intent_type=intent_type,
            actor=user,
            body=payload,
            target_id=target_id,
        ),
    )


@router.get("/asset-classes", response_model=Paginated[FaAssetClassResponse])
async def get_asset_classes(
    entity_id: uuid.UUID,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> Paginated[FaAssetClassResponse]:
    await assert_entity_access(session, user.tenant_id, entity_id, user.id, user.role)
    service = FixedAssetService(session)
    payload = await service.get_asset_classes(user.tenant_id, entity_id, skip, limit)
    return Paginated[FaAssetClassResponse](
        items=[FaAssetClassResponse.model_validate(item, from_attributes=True) for item in payload["items"]],
        total=payload["total"],
        skip=payload["skip"],
        limit=payload["limit"],
        has_more=payload["has_more"],
    )


@router.post("/asset-classes", response_model=FaAssetClassResponse)
async def create_asset_class(
    request: Request,
    body: FaAssetClassCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> FaAssetClassResponse:
    await assert_entity_access(session, user.tenant_id, body.entity_id, user.id, user.role)
    service = FixedAssetService(session)
    result = await _submit_intent(
        request,
        session,
        user=user,
        intent_type=IntentType.CREATE_FIXED_ASSET_CLASS,
        payload=body.model_dump(mode="json"),
    )
    row = (
        await service.get_asset_classes(user.tenant_id, body.entity_id, 0, 1000)
    )["items"]
    match = next(item for item in row if str(item.id) == str((result.record_refs or {}).get("asset_class_id")))
    return FaAssetClassResponse.model_validate(match, from_attributes=True).model_copy(
        update={"intent_id": result.intent_id, "job_id": result.job_id}
    )


@router.patch("/asset-classes/{asset_class_id}", response_model=FaAssetClassResponse)
async def update_asset_class(
    request: Request,
    asset_class_id: uuid.UUID,
    body: FaAssetClassUpdateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> FaAssetClassResponse:
    current = (
        await session.execute(
            select(FaAssetClass).where(
                FaAssetClass.id == asset_class_id,
                FaAssetClass.tenant_id == user.tenant_id,
            )
        )
    ).scalar_one()
    await assert_entity_access(session, user.tenant_id, current.entity_id, user.id, user.role)
    result = await _submit_intent(
        request,
        session,
        user=user,
        intent_type=IntentType.UPDATE_FIXED_ASSET_CLASS,
        payload={**body.model_dump(mode="json", exclude_unset=True), "entity_id": str(current.entity_id)},
        target_id=asset_class_id,
    )
    updated = (
        await session.execute(
            select(FaAssetClass).where(
                FaAssetClass.id == asset_class_id,
                FaAssetClass.tenant_id == user.tenant_id,
            )
        )
    ).scalar_one()
    await assert_entity_access(session, user.tenant_id, updated.entity_id, user.id, user.role)
    return FaAssetClassResponse.model_validate(updated, from_attributes=True).model_copy(
        update={"intent_id": result.intent_id, "job_id": result.job_id}
    )


@router.get("/register", response_model=list[FaRegisterLineResponse])
async def get_register(
    entity_id: uuid.UUID,
    as_of_date: date,
    gaap: str = Query(default="INDAS"),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[FaRegisterLineResponse]:
    await assert_entity_access(session, user.tenant_id, entity_id, user.id, user.role)
    service = FixedAssetService(session)
    rows = await service.get_fixed_asset_register(
        tenant_id=user.tenant_id,
        entity_id=entity_id,
        as_of_date=as_of_date,
        gaap=gaap,
    )
    return [FaRegisterLineResponse(**item) for item in rows]


@router.post("/run-period-depreciation", response_model=list[FaDepreciationRunResponse])
async def run_period_depreciation(
    request: Request,
    body: FaPeriodDepreciationRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[FaDepreciationRunResponse]:
    await assert_entity_access(session, user.tenant_id, body.entity_id, user.id, user.role)
    result = await _submit_intent(
        request,
        session,
        user=user,
        intent_type=IntentType.RUN_FIXED_ASSET_DEPRECIATION,
        payload=body.model_dump(mode="json"),
    )
    run_ids = [uuid.UUID(str(value)) for value in ((result.record_refs or {}).get("run_ids") or [])]
    rows = []
    if run_ids:
        rows = list(
            (
                await session.execute(
                    select(FaDepreciationRun).where(
                        FaDepreciationRun.tenant_id == user.tenant_id,
                        FaDepreciationRun.id.in_(run_ids),
                    )
                )
            ).scalars().all()
        )
    return [
        FaDepreciationRunResponse.model_validate(item, from_attributes=True).model_copy(
            update={"intent_id": result.intent_id, "job_id": result.job_id}
        )
        for item in rows
    ]


@router.get("", response_model=Paginated[FaAssetResponse])
async def get_assets(
    entity_id: uuid.UUID,
    status: str | None = Query(default=None),
    location_id: uuid.UUID | None = Query(default=None),
    cost_centre_id: uuid.UUID | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> Paginated[FaAssetResponse]:
    await assert_entity_access(session, user.tenant_id, entity_id, user.id, user.role)
    service = FixedAssetService(session)
    payload = await service.get_assets(
        user.tenant_id,
        entity_id,
        skip,
        limit,
        status=status,
        location_id=location_id,
        cost_centre_id=cost_centre_id,
    )
    return Paginated[FaAssetResponse](
        items=[FaAssetResponse.model_validate(item, from_attributes=True) for item in payload["items"]],
        total=payload["total"],
        skip=payload["skip"],
        limit=payload["limit"],
        has_more=payload["has_more"],
    )


@router.post("", response_model=FaAssetResponse)
async def create_asset(
    request: Request,
    body: FaAssetCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> FaAssetResponse:
    await assert_entity_access(session, user.tenant_id, body.entity_id, user.id, user.role)
    service = FixedAssetService(session)
    result = await _submit_intent(
        request,
        session,
        user=user,
        intent_type=IntentType.CREATE_FIXED_ASSET,
        payload=body.model_dump(mode="json"),
    )
    row = await service.get_asset(user.tenant_id, uuid.UUID(str((result.record_refs or {})["asset_id"])))
    return FaAssetResponse.model_validate(row, from_attributes=True).model_copy(
        update={"intent_id": result.intent_id, "job_id": result.job_id}
    )


@router.get("/{asset_id}/depreciation-history", response_model=Paginated[FaDepreciationRunResponse])
async def get_depreciation_history(
    asset_id: uuid.UUID,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> Paginated[FaDepreciationRunResponse]:
    service = FixedAssetService(session)
    asset = await service.get_asset(user.tenant_id, asset_id)
    await assert_entity_access(session, user.tenant_id, asset.entity_id, user.id, user.role)
    payload = await service.get_depreciation_history(user.tenant_id, asset_id, skip, limit)
    return Paginated[FaDepreciationRunResponse](
        items=[FaDepreciationRunResponse.model_validate(item, from_attributes=True) for item in payload["items"]],
        total=payload["total"],
        skip=payload["skip"],
        limit=payload["limit"],
        has_more=payload["has_more"],
    )


@router.post("/{asset_id}/depreciation-run", response_model=FaDepreciationRunResponse)
async def run_asset_depreciation(
    request: Request,
    asset_id: uuid.UUID,
    body: FaDepreciationRunRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> FaDepreciationRunResponse:
    service = FixedAssetService(session)
    asset = await service.get_asset(user.tenant_id, asset_id)
    await assert_entity_access(session, user.tenant_id, asset.entity_id, user.id, user.role)
    result = await _submit_intent(
        request,
        session,
        user=user,
        intent_type=IntentType.RUN_FIXED_ASSET_DEPRECIATION,
        payload={**body.model_dump(mode="json"), "entity_id": str(asset.entity_id)},
        target_id=asset_id,
    )
    row = (
        await session.execute(
            select(FaDepreciationRun).where(
                FaDepreciationRun.id == uuid.UUID(str((result.record_refs or {})["run_id"])),
                FaDepreciationRun.tenant_id == user.tenant_id,
            )
        )
    ).scalar_one()
    return FaDepreciationRunResponse.model_validate(row, from_attributes=True).model_copy(
        update={"intent_id": result.intent_id, "job_id": result.job_id}
    )


@router.post("/{asset_id}/revaluation", response_model=FaRevaluationResponse)
async def post_revaluation(
    request: Request,
    asset_id: uuid.UUID,
    body: FaRevaluationRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> FaRevaluationResponse:
    service = FixedAssetService(session)
    asset = await service.get_asset(user.tenant_id, asset_id)
    await assert_entity_access(session, user.tenant_id, asset.entity_id, user.id, user.role)
    result = await _submit_intent(
        request,
        session,
        user=user,
        intent_type=IntentType.POST_FIXED_ASSET_REVALUATION,
        payload={**body.model_dump(mode="json"), "entity_id": str(asset.entity_id)},
        target_id=asset_id,
    )
    row = (
        await session.execute(
            select(FaRevaluation).where(
                FaRevaluation.id == uuid.UUID(str((result.record_refs or {})["revaluation_id"])),
                FaRevaluation.tenant_id == user.tenant_id,
            )
        )
    ).scalar_one()
    return FaRevaluationResponse.model_validate(row, from_attributes=True).model_copy(
        update={"intent_id": result.intent_id, "job_id": result.job_id}
    )


@router.get("/{asset_id}/revaluation-history", response_model=list[FaRevaluationResponse])
async def get_revaluation_history(
    asset_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[FaRevaluationResponse]:
    service = FixedAssetService(session)
    asset = await service.get_asset(user.tenant_id, asset_id)
    await assert_entity_access(session, user.tenant_id, asset.entity_id, user.id, user.role)
    rows = await service.get_revaluation_history(user.tenant_id, asset_id)
    return [FaRevaluationResponse.model_validate(item, from_attributes=True) for item in rows]


@router.post("/{asset_id}/impairment", response_model=FaImpairmentResponse)
async def post_impairment(
    request: Request,
    asset_id: uuid.UUID,
    body: FaImpairmentRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> FaImpairmentResponse:
    service = FixedAssetService(session)
    asset = await service.get_asset(user.tenant_id, asset_id)
    await assert_entity_access(session, user.tenant_id, asset.entity_id, user.id, user.role)
    result = await _submit_intent(
        request,
        session,
        user=user,
        intent_type=IntentType.POST_FIXED_ASSET_IMPAIRMENT,
        payload={**body.model_dump(mode="json"), "entity_id": str(asset.entity_id)},
        target_id=asset_id,
    )
    row = (
        await session.execute(
            select(FaImpairment).where(
                FaImpairment.id == uuid.UUID(str((result.record_refs or {})["impairment_id"])),
                FaImpairment.tenant_id == user.tenant_id,
            )
        )
    ).scalar_one()
    return FaImpairmentResponse.model_validate(row, from_attributes=True).model_copy(
        update={"intent_id": result.intent_id, "job_id": result.job_id}
    )


@router.post("/{asset_id}/dispose", response_model=FaAssetResponse)
async def dispose_asset(
    request: Request,
    asset_id: uuid.UUID,
    body: FaDisposalRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> FaAssetResponse:
    service = FixedAssetService(session)
    asset = await service.get_asset(user.tenant_id, asset_id)
    await assert_entity_access(session, user.tenant_id, asset.entity_id, user.id, user.role)
    result = await _submit_intent(
        request,
        session,
        user=user,
        intent_type=IntentType.DISPOSE_FIXED_ASSET,
        payload={**body.model_dump(mode="json"), "entity_id": str(asset.entity_id)},
        target_id=asset_id,
    )
    row = await service.get_asset(user.tenant_id, asset_id)
    return FaAssetResponse.model_validate(row, from_attributes=True).model_copy(
        update={"intent_id": result.intent_id, "job_id": result.job_id}
    )


@router.get("/{asset_id}/impairment-history", response_model=list[FaImpairmentResponse])
async def get_impairment_history(
    asset_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[FaImpairmentResponse]:
    service = FixedAssetService(session)
    asset = await service.get_asset(user.tenant_id, asset_id)
    await assert_entity_access(session, user.tenant_id, asset.entity_id, user.id, user.role)
    rows = await service.get_impairment_history(user.tenant_id, asset_id)
    return [FaImpairmentResponse.model_validate(item, from_attributes=True) for item in rows]


@router.get("/{asset_id}", response_model=FaAssetResponse)
async def get_asset(
    asset_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> FaAssetResponse:
    service = FixedAssetService(session)
    row = await service.get_asset(user.tenant_id, asset_id)
    await assert_entity_access(session, user.tenant_id, row.entity_id, user.id, user.role)
    return FaAssetResponse.model_validate(row, from_attributes=True)


@router.patch("/{asset_id}", response_model=FaAssetResponse)
async def update_asset(
    request: Request,
    asset_id: uuid.UUID,
    body: FaAssetUpdateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> FaAssetResponse:
    service = FixedAssetService(session)
    current = await service.get_asset(user.tenant_id, asset_id)
    await assert_entity_access(session, user.tenant_id, current.entity_id, user.id, user.role)
    result = await _submit_intent(
        request,
        session,
        user=user,
        intent_type=IntentType.UPDATE_FIXED_ASSET,
        payload={**body.model_dump(mode="json", exclude_unset=True), "entity_id": str(current.entity_id)},
        target_id=asset_id,
    )
    row = await service.get_asset(user.tenant_id, asset_id)
    return FaAssetResponse.model_validate(row, from_attributes=True).model_copy(
        update={"intent_id": result.intent_id, "job_id": result.job_id}
    )


__all__ = ["router"]
