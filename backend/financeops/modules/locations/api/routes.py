from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user
from financeops.db.models.users import IamUser
from financeops.modules.locations.api.schemas import (
    CostCentreCreateRequest,
    CostCentreResponse,
    CostCentreTreeNode,
    CostCentreUpdateRequest,
    GstinValidationResponse,
    LocationCreateRequest,
    LocationResponse,
    LocationUpdateRequest,
    StateCodeResponse,
)
from financeops.modules.locations.application.location_service import LocationService
from financeops.platform.services.tenancy.entity_access import assert_entity_access
from financeops.shared_kernel.pagination import Paginated
from financeops.utils.gstin import INDIA_STATE_CODES, extract_state_code, validate_gstin

router = APIRouter(prefix="/locations", tags=["locations"])


@router.get("", response_model=Paginated[LocationResponse])
async def get_locations(
    entity_id: uuid.UUID,
    is_active: bool | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> Paginated[LocationResponse]:
    await assert_entity_access(session, user.tenant_id, entity_id, user.id, user.role)
    service = LocationService(session)
    payload = await service.get_locations(
        user.tenant_id,
        entity_id,
        skip=skip,
        limit=limit,
        is_active=is_active,
    )
    return Paginated[LocationResponse](
        items=[
            LocationResponse.model_validate(row, from_attributes=True)
            for row in payload["items"]
        ],
        total=payload["total"],
        skip=payload["skip"],
        limit=payload["limit"],
        has_more=payload["has_more"],
    )


@router.post("", response_model=LocationResponse)
async def create_location(
    body: LocationCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> LocationResponse:
    await assert_entity_access(session, user.tenant_id, body.entity_id, user.id, user.role)
    service = LocationService(session)
    row = await service.create_location(
        user.tenant_id,
        body.entity_id,
        body.model_dump(exclude={"entity_id"}),
    )
    return LocationResponse.model_validate(row, from_attributes=True)


@router.patch("/{location_id}", response_model=LocationResponse)
async def patch_location(
    location_id: uuid.UUID,
    body: LocationUpdateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> LocationResponse:
    service = LocationService(session)
    current = await service.get_location(user.tenant_id, location_id)
    await assert_entity_access(session, user.tenant_id, current.entity_id, user.id, user.role)
    row = await service.update_location(
        user.tenant_id,
        location_id,
        body.model_dump(exclude_unset=True),
    )
    return LocationResponse.model_validate(row, from_attributes=True)


@router.post("/{location_id}/set-primary", response_model=LocationResponse)
async def set_primary_location(
    location_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> LocationResponse:
    service = LocationService(session)
    current = await service.get_location(user.tenant_id, location_id)
    await assert_entity_access(session, user.tenant_id, current.entity_id, user.id, user.role)
    row = await service.set_primary_location(user.tenant_id, current.entity_id, location_id)
    return LocationResponse.model_validate(row, from_attributes=True)


@router.get("/cost-centres", response_model=Paginated[CostCentreResponse])
async def get_cost_centres(
    entity_id: uuid.UUID,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> Paginated[CostCentreResponse]:
    await assert_entity_access(session, user.tenant_id, entity_id, user.id, user.role)
    service = LocationService(session)
    payload = await service.get_cost_centres(
        user.tenant_id,
        entity_id,
        skip=skip,
        limit=limit,
    )
    return Paginated[CostCentreResponse](
        items=[
            CostCentreResponse.model_validate(row, from_attributes=True)
            for row in payload["items"]
        ],
        total=payload["total"],
        skip=payload["skip"],
        limit=payload["limit"],
        has_more=payload["has_more"],
    )


@router.post("/cost-centres", response_model=CostCentreResponse)
async def create_cost_centre(
    body: CostCentreCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> CostCentreResponse:
    await assert_entity_access(session, user.tenant_id, body.entity_id, user.id, user.role)
    service = LocationService(session)
    row = await service.create_cost_centre(
        user.tenant_id,
        body.entity_id,
        body.model_dump(exclude={"entity_id"}),
    )
    return CostCentreResponse.model_validate(row, from_attributes=True)


@router.patch("/cost-centres/{cost_centre_id}", response_model=CostCentreResponse)
async def patch_cost_centre(
    cost_centre_id: uuid.UUID,
    body: CostCentreUpdateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> CostCentreResponse:
    service = LocationService(session)
    current = await service.get_cost_centre(user.tenant_id, cost_centre_id)
    await assert_entity_access(session, user.tenant_id, current.entity_id, user.id, user.role)
    row = await service.update_cost_centre(
        user.tenant_id,
        cost_centre_id,
        body.model_dump(exclude_unset=True),
    )
    return CostCentreResponse.model_validate(row, from_attributes=True)


@router.get("/cost-centres/tree", response_model=list[CostCentreTreeNode])
async def get_cost_centre_tree(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[CostCentreTreeNode]:
    await assert_entity_access(session, user.tenant_id, entity_id, user.id, user.role)
    service = LocationService(session)
    payload = await service.get_cost_centre_tree(user.tenant_id, entity_id)
    return [CostCentreTreeNode(**item) for item in payload]


@router.get("/validate-gstin", response_model=GstinValidationResponse)
async def validate_gstin_endpoint(gstin: str) -> GstinValidationResponse:
    valid = validate_gstin(gstin)
    if not valid:
        return GstinValidationResponse(valid=False, state_code=None, state_name=None)
    code = extract_state_code(gstin)
    return GstinValidationResponse(
        valid=True,
        state_code=code,
        state_name=INDIA_STATE_CODES.get(code or ""),
    )


@router.get("/state-codes", response_model=list[StateCodeResponse])
async def get_state_codes() -> list[StateCodeResponse]:
    return [
        StateCodeResponse(code=code, name=name)
        for code, name in sorted(INDIA_STATE_CODES.items())
    ]


@router.get("/{location_id}", response_model=LocationResponse)
async def get_location(
    location_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> LocationResponse:
    service = LocationService(session)
    row = await service.get_location(user.tenant_id, location_id)
    await assert_entity_access(session, user.tenant_id, row.entity_id, user.id, user.role)
    return LocationResponse.model_validate(row, from_attributes=True)


__all__ = ["router"]
