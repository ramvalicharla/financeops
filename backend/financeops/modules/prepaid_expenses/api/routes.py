from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user
from financeops.db.models.users import IamUser
from financeops.modules.prepaid_expenses.api.schemas import (
    PrepaidAmortisationEntryResponse,
    PrepaidRunPeriodRequest,
    PrepaidScheduleCreateRequest,
    PrepaidScheduleLineResponse,
    PrepaidScheduleResponse,
    PrepaidScheduleUpdateRequest,
)
from financeops.modules.prepaid_expenses.application.prepaid_service import PrepaidService
from financeops.platform.services.tenancy.entity_access import assert_entity_access
from financeops.shared_kernel.pagination import Paginated

router = APIRouter(prefix="/prepaid", tags=["prepaid"])


@router.get("", response_model=Paginated[PrepaidScheduleResponse])
async def get_schedules(
    entity_id: uuid.UUID,
    status: str | None = Query(default=None),
    prepaid_type: str | None = Query(default=None),
    location_id: uuid.UUID | None = Query(default=None),
    cost_centre_id: uuid.UUID | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> Paginated[PrepaidScheduleResponse]:
    await assert_entity_access(session, user.tenant_id, entity_id, user.id, user.role)
    service = PrepaidService(session)
    payload = await service.get_schedules(
        tenant_id=user.tenant_id,
        entity_id=entity_id,
        skip=skip,
        limit=limit,
        status=status,
        prepaid_type=prepaid_type,
        location_id=location_id,
        cost_centre_id=cost_centre_id,
    )
    return Paginated[PrepaidScheduleResponse](
        items=[PrepaidScheduleResponse.model_validate(item, from_attributes=True) for item in payload["items"]],
        total=payload["total"],
        skip=payload["skip"],
        limit=payload["limit"],
        has_more=payload["has_more"],
    )


@router.post("", response_model=PrepaidScheduleResponse)
async def create_schedule(
    body: PrepaidScheduleCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> PrepaidScheduleResponse:
    await assert_entity_access(session, user.tenant_id, body.entity_id, user.id, user.role)
    service = PrepaidService(session)
    row = await service.create_schedule(
        tenant_id=user.tenant_id,
        entity_id=body.entity_id,
        data=body.model_dump(exclude={"entity_id"}),
    )
    return PrepaidScheduleResponse.model_validate(row, from_attributes=True)


@router.get("/{schedule_id}", response_model=PrepaidScheduleResponse)
async def get_schedule(
    schedule_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> PrepaidScheduleResponse:
    service = PrepaidService(session)
    row = await service.get_schedule(user.tenant_id, schedule_id)
    await assert_entity_access(session, user.tenant_id, row.entity_id, user.id, user.role)
    return PrepaidScheduleResponse.model_validate(row, from_attributes=True)


@router.patch("/{schedule_id}", response_model=PrepaidScheduleResponse)
async def patch_schedule(
    schedule_id: uuid.UUID,
    body: PrepaidScheduleUpdateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> PrepaidScheduleResponse:
    service = PrepaidService(session)
    current = await service.get_schedule(user.tenant_id, schedule_id)
    await assert_entity_access(session, user.tenant_id, current.entity_id, user.id, user.role)
    row = await service.update_schedule(
        tenant_id=user.tenant_id,
        schedule_id=schedule_id,
        data=body.model_dump(exclude_unset=True),
    )
    return PrepaidScheduleResponse.model_validate(row, from_attributes=True)


@router.get("/{schedule_id}/schedule", response_model=list[PrepaidScheduleLineResponse])
async def get_amortisation_schedule(
    schedule_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[PrepaidScheduleLineResponse]:
    service = PrepaidService(session)
    current = await service.get_schedule(user.tenant_id, schedule_id)
    await assert_entity_access(session, user.tenant_id, current.entity_id, user.id, user.role)
    rows = await service.get_amortisation_schedule(user.tenant_id, schedule_id)
    return [PrepaidScheduleLineResponse(**item) for item in rows]


@router.get("/{schedule_id}/entries", response_model=Paginated[PrepaidAmortisationEntryResponse])
async def get_entries(
    schedule_id: uuid.UUID,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> Paginated[PrepaidAmortisationEntryResponse]:
    service = PrepaidService(session)
    current = await service.get_schedule(user.tenant_id, schedule_id)
    await assert_entity_access(session, user.tenant_id, current.entity_id, user.id, user.role)
    payload = await service.get_entries(user.tenant_id, schedule_id, skip, limit)
    return Paginated[PrepaidAmortisationEntryResponse](
        items=[
            PrepaidAmortisationEntryResponse.model_validate(item, from_attributes=True)
            for item in payload["items"]
        ],
        total=payload["total"],
        skip=payload["skip"],
        limit=payload["limit"],
        has_more=payload["has_more"],
    )


@router.post("/run-period", response_model=list[PrepaidAmortisationEntryResponse])
async def run_period(
    body: PrepaidRunPeriodRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[PrepaidAmortisationEntryResponse]:
    await assert_entity_access(session, user.tenant_id, body.entity_id, user.id, user.role)
    service = PrepaidService(session)
    rows = await service.run_period(
        tenant_id=user.tenant_id,
        entity_id=body.entity_id,
        period_start=body.period_start,
        period_end=body.period_end,
    )
    return [PrepaidAmortisationEntryResponse.model_validate(item, from_attributes=True) for item in rows]


__all__ = ["router"]
