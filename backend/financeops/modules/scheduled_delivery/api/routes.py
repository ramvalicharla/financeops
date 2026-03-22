from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user
from financeops.db.models.scheduled_delivery import DeliveryLog, DeliverySchedule
from financeops.db.models.users import IamUser
from financeops.modules.scheduled_delivery.domain.enums import (
    ChannelType,
    DeliveryExportFormat,
    ScheduleType,
)
from financeops.modules.scheduled_delivery.domain.schedule_definition import (
    Recipient,
    ScheduleDefinitionSchema,
)
from financeops.modules.scheduled_delivery.infrastructure.repository import (
    DeliveryRepository,
)
from financeops.modules.scheduled_delivery.tasks import deliver_schedule_task
from financeops.shared_kernel.pagination import Paginated

router = APIRouter(prefix="/delivery", tags=["delivery"])


class CreateScheduleRequest(BaseModel):
    name: str
    description: str | None = None
    schedule_type: ScheduleType
    source_definition_id: uuid.UUID
    cron_expression: str
    timezone: str = "UTC"
    recipients: list[Recipient]
    export_format: DeliveryExportFormat = DeliveryExportFormat.PDF
    config: dict[str, Any] = Field(default_factory=dict)


class UpdateScheduleRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    schedule_type: ScheduleType | None = None
    source_definition_id: uuid.UUID | None = None
    cron_expression: str | None = None
    timezone: str | None = None
    recipients: list[Recipient] | None = None
    export_format: DeliveryExportFormat | None = None
    is_active: bool | None = None
    config: dict[str, Any] | None = None


class ScheduleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    description: str | None = None
    schedule_type: str
    source_definition_id: uuid.UUID
    cron_expression: str
    timezone: str
    recipients: list[dict[str, str]]
    export_format: str
    is_active: bool
    last_triggered_at: datetime | None = None
    next_run_at: datetime | None = None
    config: dict[str, Any]
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime


class DeliveryLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    schedule_id: uuid.UUID
    triggered_at: datetime
    completed_at: datetime | None = None
    status: str
    channel_type: str
    recipient_address: str
    source_run_id: uuid.UUID | None = None
    error_message: str | None = None
    retry_count: int
    response_metadata: dict[str, Any]
    created_at: datetime


class TriggerResponse(BaseModel):
    schedule_id: str
    status: str


@router.post("/schedules", response_model=ScheduleResponse, status_code=status.HTTP_201_CREATED)
async def create_schedule(
    body: CreateScheduleRequest,
    db: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> ScheduleResponse:
    repository = DeliveryRepository()
    schema = ScheduleDefinitionSchema(
        name=body.name,
        description=body.description,
        schedule_type=body.schedule_type,
        source_definition_id=body.source_definition_id,
        cron_expression=body.cron_expression,
        timezone=body.timezone,
        recipients=body.recipients,
        export_format=body.export_format,
        config=body.config,
    )
    row = await repository.create_schedule(
        db=db,
        tenant_id=user.tenant_id,
        schema=schema,
        created_by=user.id,
        next_run_at=datetime.now(UTC),
    )
    await db.commit()
    return ScheduleResponse.model_validate(row)


@router.get("/schedules", response_model=Paginated[ScheduleResponse] | list[ScheduleResponse])
async def list_schedules(
    request: Request,
    active_only: bool = Query(default=False),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> Paginated[ScheduleResponse] | list[ScheduleResponse]:
    repository = DeliveryRepository()
    base_stmt = select(DeliverySchedule).where(DeliverySchedule.tenant_id == user.tenant_id)
    if active_only:
        base_stmt = base_stmt.where(DeliverySchedule.is_active.is_(True))
    total = (await db.execute(select(func.count()).select_from(base_stmt.subquery()))).scalar_one()
    rows = (
        await db.execute(
            base_stmt
            .order_by(DeliverySchedule.created_at.desc(), DeliverySchedule.id.desc())
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()
    data = [ScheduleResponse.model_validate(row) for row in rows]
    if "limit" not in request.query_params and "offset" not in request.query_params:
        return data
    return Paginated[ScheduleResponse](data=data, total=int(total), limit=limit, offset=offset)


@router.get("/schedules/{id}", response_model=ScheduleResponse)
async def get_schedule(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> ScheduleResponse:
    repository = DeliveryRepository()
    row = await repository.get_schedule(db=db, tenant_id=user.tenant_id, schedule_id=id)
    if row is None:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return ScheduleResponse.model_validate(row)


@router.patch("/schedules/{id}", response_model=ScheduleResponse)
async def update_schedule(
    id: uuid.UUID,
    body: UpdateScheduleRequest,
    db: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> ScheduleResponse:
    repository = DeliveryRepository()
    existing = await repository.get_schedule(db=db, tenant_id=user.tenant_id, schedule_id=id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Schedule not found")

    updates = body.model_dump(exclude_unset=True)
    if "schedule_type" in updates and updates["schedule_type"] is not None:
        updates["schedule_type"] = updates["schedule_type"].value
    if "export_format" in updates and updates["export_format"] is not None:
        updates["export_format"] = updates["export_format"].value
    if "recipients" in updates and updates["recipients"] is not None:
        normalized_recipients: list[dict[str, str]] = []
        for recipient in updates["recipients"]:
            if isinstance(recipient, Recipient):
                normalized_recipients.append(recipient.model_dump(mode="json"))
            else:
                normalized_recipients.append(dict(recipient))
        updates["recipients"] = normalized_recipients

    row = await repository.update_schedule(
        db=db,
        tenant_id=user.tenant_id,
        schedule_id=id,
        updates=updates,
    )
    await db.commit()
    return ScheduleResponse.model_validate(row)


@router.delete("/schedules/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> Response:
    repository = DeliveryRepository()
    existing = await repository.get_schedule(db=db, tenant_id=user.tenant_id, schedule_id=id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Schedule not found")
    await repository.deactivate_schedule(db=db, tenant_id=user.tenant_id, schedule_id=id)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/schedules/{id}/trigger", response_model=TriggerResponse, status_code=status.HTTP_202_ACCEPTED)
async def trigger_schedule(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> TriggerResponse:
    repository = DeliveryRepository()
    existing = await repository.get_schedule(db=db, tenant_id=user.tenant_id, schedule_id=id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Schedule not found")
    if not existing.is_active:
        raise HTTPException(status_code=400, detail="Schedule is inactive")

    deliver_schedule_task.delay(str(id), str(user.tenant_id))
    return TriggerResponse(schedule_id=str(id), status="triggered")


@router.get("/logs", response_model=Paginated[DeliveryLogResponse] | list[DeliveryLogResponse])
async def list_logs(
    request: Request,
    schedule_id: uuid.UUID | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> Paginated[DeliveryLogResponse] | list[DeliveryLogResponse]:
    repository = DeliveryRepository()
    base_stmt = select(DeliveryLog).where(DeliveryLog.tenant_id == user.tenant_id)
    if schedule_id:
        base_stmt = base_stmt.where(DeliveryLog.schedule_id == schedule_id)
    if status_filter:
        base_stmt = base_stmt.where(DeliveryLog.status == status_filter)
    total = (await db.execute(select(func.count()).select_from(base_stmt.subquery()))).scalar_one()
    rows = await repository.list_logs(
        db=db,
        tenant_id=user.tenant_id,
        schedule_id=schedule_id,
        status=status_filter,
        limit=limit + offset,
    )
    paged_rows = rows[offset : offset + limit]
    data = [DeliveryLogResponse.model_validate(row) for row in paged_rows]
    if "limit" not in request.query_params and "offset" not in request.query_params:
        return data
    return Paginated[DeliveryLogResponse](data=data, total=int(total), limit=limit, offset=offset)


@router.get("/logs/{id}", response_model=DeliveryLogResponse)
async def get_log(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> DeliveryLogResponse:
    repository = DeliveryRepository()
    row = await repository.get_log(db=db, tenant_id=user.tenant_id, log_id=id)
    if row is None:
        raise HTTPException(status_code=404, detail="Delivery log not found")
    return DeliveryLogResponse.model_validate(row)
