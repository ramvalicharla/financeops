from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user
from financeops.core.intent.api import build_idempotency_key, build_intent_actor
from financeops.core.intent.enums import IntentType
from financeops.core.intent.service import IntentService
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
from financeops.modules.prepaid_expenses.models import PrepaidAmortisationEntry
from financeops.platform.services.tenancy.entity_access import assert_entity_access
from financeops.shared_kernel.pagination import Paginated

router = APIRouter(prefix="/prepaid", tags=["prepaid"])


async def _submit_intent(
    request: Request,
    session: AsyncSession,
    *,
    user: IamUser,
    intent_type: IntentType,
    payload: dict,
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
    request: Request,
    body: PrepaidScheduleCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> PrepaidScheduleResponse:
    await assert_entity_access(session, user.tenant_id, body.entity_id, user.id, user.role)
    service = PrepaidService(session)
    result = await _submit_intent(
        request,
        session,
        user=user,
        intent_type=IntentType.CREATE_PREPAID_SCHEDULE,
        payload=body.model_dump(mode="json"),
    )
    row = await service.get_schedule(user.tenant_id, uuid.UUID(str((result.record_refs or {})["schedule_id"])))
    return PrepaidScheduleResponse.model_validate(row, from_attributes=True).model_copy(
        update={"intent_id": result.intent_id, "job_id": result.job_id}
    )


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
    request: Request,
    schedule_id: uuid.UUID,
    body: PrepaidScheduleUpdateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> PrepaidScheduleResponse:
    service = PrepaidService(session)
    current = await service.get_schedule(user.tenant_id, schedule_id)
    await assert_entity_access(session, user.tenant_id, current.entity_id, user.id, user.role)
    result = await _submit_intent(
        request,
        session,
        user=user,
        intent_type=IntentType.UPDATE_PREPAID_SCHEDULE,
        payload={**body.model_dump(mode="json", exclude_unset=True), "entity_id": str(current.entity_id)},
        target_id=schedule_id,
    )
    row = await service.get_schedule(user.tenant_id, schedule_id)
    return PrepaidScheduleResponse.model_validate(row, from_attributes=True).model_copy(
        update={"intent_id": result.intent_id, "job_id": result.job_id}
    )


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
    request: Request,
    body: PrepaidRunPeriodRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[PrepaidAmortisationEntryResponse]:
    await assert_entity_access(session, user.tenant_id, body.entity_id, user.id, user.role)
    result = await _submit_intent(
        request,
        session,
        user=user,
        intent_type=IntentType.POST_PREPAID_AMORTIZATION,
        payload=body.model_dump(mode="json"),
    )
    entry_ids = [uuid.UUID(str(value)) for value in ((result.record_refs or {}).get("entry_ids") or [])]
    rows = []
    if entry_ids:
        rows = list(
            (
                await session.execute(
                    select(PrepaidAmortisationEntry).where(
                        PrepaidAmortisationEntry.tenant_id == user.tenant_id,
                        PrepaidAmortisationEntry.id.in_(entry_ids),
                    )
                )
            ).scalars().all()
        )
    return [
        PrepaidAmortisationEntryResponse.model_validate(item, from_attributes=True).model_copy(
            update={"intent_id": result.intent_id, "job_id": result.job_id}
        )
        for item in rows
    ]


__all__ = ["router"]
