from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user
from financeops.db.models.users import IamUser
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
    body: FaAssetClassCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> FaAssetClassResponse:
    await assert_entity_access(session, user.tenant_id, body.entity_id, user.id, user.role)
    service = FixedAssetService(session)
    row = await service.create_asset_class(
        user.tenant_id,
        body.entity_id,
        body.model_dump(exclude={"entity_id"}),
    )
    return FaAssetClassResponse.model_validate(row, from_attributes=True)


@router.patch("/asset-classes/{asset_class_id}", response_model=FaAssetClassResponse)
async def update_asset_class(
    asset_class_id: uuid.UUID,
    body: FaAssetClassUpdateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> FaAssetClassResponse:
    service = FixedAssetService(session)
    row = await service.update_asset_class(
        user.tenant_id,
        asset_class_id,
        body.model_dump(exclude_unset=True),
    )
    await assert_entity_access(session, user.tenant_id, row.entity_id, user.id, user.role)
    return FaAssetClassResponse.model_validate(row, from_attributes=True)


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
    body: FaPeriodDepreciationRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[FaDepreciationRunResponse]:
    await assert_entity_access(session, user.tenant_id, body.entity_id, user.id, user.role)
    service = FixedAssetService(session)
    rows = await service.run_depreciation(
        tenant_id=user.tenant_id,
        entity_id=body.entity_id,
        period_start=body.period_start,
        period_end=body.period_end,
        gaap=body.gaap,
    )
    return [FaDepreciationRunResponse.model_validate(item, from_attributes=True) for item in rows]


@router.get("", response_model=Paginated[FaAssetResponse])
async def get_assets(
    entity_id: uuid.UUID,
    status: str | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> Paginated[FaAssetResponse]:
    await assert_entity_access(session, user.tenant_id, entity_id, user.id, user.role)
    service = FixedAssetService(session)
    payload = await service.get_assets(user.tenant_id, entity_id, skip, limit, status=status)
    return Paginated[FaAssetResponse](
        items=[FaAssetResponse.model_validate(item, from_attributes=True) for item in payload["items"]],
        total=payload["total"],
        skip=payload["skip"],
        limit=payload["limit"],
        has_more=payload["has_more"],
    )


@router.post("", response_model=FaAssetResponse)
async def create_asset(
    body: FaAssetCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> FaAssetResponse:
    await assert_entity_access(session, user.tenant_id, body.entity_id, user.id, user.role)
    service = FixedAssetService(session)
    row = await service.create_asset(
        tenant_id=user.tenant_id,
        entity_id=body.entity_id,
        data=body.model_dump(exclude={"entity_id"}),
    )
    return FaAssetResponse.model_validate(row, from_attributes=True)


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
    asset_id: uuid.UUID,
    body: FaDepreciationRunRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> FaDepreciationRunResponse:
    service = FixedAssetService(session)
    asset = await service.get_asset(user.tenant_id, asset_id)
    await assert_entity_access(session, user.tenant_id, asset.entity_id, user.id, user.role)
    row = await service.run_asset_depreciation(
        tenant_id=user.tenant_id,
        asset_id=asset_id,
        period_start=body.period_start,
        period_end=body.period_end,
        gaap=body.gaap,
    )
    return FaDepreciationRunResponse.model_validate(row, from_attributes=True)


@router.post("/{asset_id}/revaluation", response_model=FaRevaluationResponse)
async def post_revaluation(
    asset_id: uuid.UUID,
    body: FaRevaluationRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> FaRevaluationResponse:
    service = FixedAssetService(session)
    asset = await service.get_asset(user.tenant_id, asset_id)
    await assert_entity_access(session, user.tenant_id, asset.entity_id, user.id, user.role)
    row = await service.post_revaluation(
        tenant_id=user.tenant_id,
        asset_id=asset_id,
        fair_value=body.fair_value,
        method=body.method,
        revaluation_date=body.revaluation_date,
    )
    return FaRevaluationResponse.model_validate(row, from_attributes=True)


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
    asset_id: uuid.UUID,
    body: FaImpairmentRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> FaImpairmentResponse:
    service = FixedAssetService(session)
    asset = await service.get_asset(user.tenant_id, asset_id)
    await assert_entity_access(session, user.tenant_id, asset.entity_id, user.id, user.role)
    row = await service.post_impairment(
        tenant_id=user.tenant_id,
        asset_id=asset_id,
        value_in_use=body.value_in_use,
        fvlcts=body.fvlcts,
        discount_rate=body.discount_rate,
        impairment_date=body.impairment_date,
    )
    return FaImpairmentResponse.model_validate(row, from_attributes=True)


@router.post("/{asset_id}/dispose", response_model=FaAssetResponse)
async def dispose_asset(
    asset_id: uuid.UUID,
    body: FaDisposalRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> FaAssetResponse:
    service = FixedAssetService(session)
    asset = await service.get_asset(user.tenant_id, asset_id)
    await assert_entity_access(session, user.tenant_id, asset.entity_id, user.id, user.role)
    row = await service.dispose_asset(
        tenant_id=user.tenant_id,
        asset_id=asset_id,
        disposal_date=body.disposal_date,
        proceeds=body.proceeds,
    )
    return FaAssetResponse.model_validate(row, from_attributes=True)


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
    asset_id: uuid.UUID,
    body: FaAssetUpdateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> FaAssetResponse:
    service = FixedAssetService(session)
    current = await service.get_asset(user.tenant_id, asset_id)
    await assert_entity_access(session, user.tenant_id, current.entity_id, user.id, user.role)
    row = await service.update_asset(
        tenant_id=user.tenant_id,
        asset_id=asset_id,
        data=body.model_dump(exclude_unset=True),
    )
    return FaAssetResponse.model_validate(row, from_attributes=True)


__all__ = ["router"]
