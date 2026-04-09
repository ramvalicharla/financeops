from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user
from financeops.core.intent.dispatcher import JobDispatcher
from financeops.db.models.users import IamUser
from financeops.modules.auto_trigger.models import PipelineRun, PipelineStepLog
from financeops.modules.auto_trigger.pipeline import (
    resolve_pipeline_run_id_for_trigger,
    trigger_post_sync_pipeline,
)
from financeops.shared_kernel.pagination import Paginated

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


class PipelineStepLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    pipeline_run_id: uuid.UUID
    tenant_id: uuid.UUID
    step_name: str
    status: str
    started_at: datetime
    completed_at: datetime | None = None
    error_message: str | None = None
    result_summary: dict[str, Any] | None = None
    created_at: datetime


class PipelineRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    sync_run_id: uuid.UUID
    status: str
    triggered_at: datetime
    completed_at: datetime | None = None
    error_message: str | None = None
    created_at: datetime


class PipelineRunDetailResponse(PipelineRunResponse):
    step_logs: list[PipelineStepLogResponse] = Field(default_factory=list)


class TriggerPipelineRequest(BaseModel):
    sync_run_id: uuid.UUID


class TriggerPipelineResponse(BaseModel):
    pipeline_run_id: str
    status: str


@router.get("/runs", response_model=Paginated[PipelineRunResponse] | list[PipelineRunResponse])
async def list_pipeline_runs(
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> Paginated[PipelineRunResponse] | list[PipelineRunResponse]:
    total = (
        await db.execute(
            select(func.count()).select_from(
                select(PipelineRun).where(PipelineRun.tenant_id == user.tenant_id).subquery()
            )
        )
    ).scalar_one()
    rows = (
        await db.execute(
            select(PipelineRun)
            .where(PipelineRun.tenant_id == user.tenant_id)
            .order_by(PipelineRun.triggered_at.desc(), PipelineRun.id.desc())
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()
    data = [PipelineRunResponse.model_validate(row) for row in rows]
    if "limit" not in request.query_params and "offset" not in request.query_params:
        return data
    return Paginated[PipelineRunResponse](data=data, total=int(total), limit=limit, offset=offset)


async def _get_pipeline_run_owned_by_tenant(
    *,
    db: AsyncSession,
    pipeline_run_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> PipelineRun:
    row = (
        await db.execute(
            select(PipelineRun).where(
                PipelineRun.id == pipeline_run_id,
                PipelineRun.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    return row


@router.get("/runs/{pipeline_run_id}", response_model=PipelineRunDetailResponse)
async def get_pipeline_run_detail(
    pipeline_run_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> PipelineRunDetailResponse:
    row = await _get_pipeline_run_owned_by_tenant(
        db=db,
        pipeline_run_id=pipeline_run_id,
        tenant_id=user.tenant_id,
    )
    logs = (
        await db.execute(
            select(PipelineStepLog)
            .where(
                PipelineStepLog.pipeline_run_id == row.id,
                PipelineStepLog.tenant_id == user.tenant_id,
            )
            .order_by(PipelineStepLog.created_at.desc(), PipelineStepLog.id.desc())
            .limit(100)
        )
    ).scalars().all()
    return PipelineRunDetailResponse(
        **PipelineRunResponse.model_validate(row).model_dump(),
        step_logs=[PipelineStepLogResponse.model_validate(log) for log in logs],
    )


@router.get("/runs/{pipeline_run_id}/steps", response_model=Paginated[PipelineStepLogResponse] | list[PipelineStepLogResponse])
async def get_pipeline_run_steps(
    request: Request,
    pipeline_run_id: uuid.UUID,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> Paginated[PipelineStepLogResponse] | list[PipelineStepLogResponse]:
    _ = await _get_pipeline_run_owned_by_tenant(
        db=db,
        pipeline_run_id=pipeline_run_id,
        tenant_id=user.tenant_id,
    )
    total = (
        await db.execute(
            select(func.count()).select_from(
                select(PipelineStepLog)
                .where(
                    PipelineStepLog.pipeline_run_id == pipeline_run_id,
                    PipelineStepLog.tenant_id == user.tenant_id,
                )
                .subquery()
            )
        )
    ).scalar_one()
    logs = (
        await db.execute(
            select(PipelineStepLog)
            .where(
                PipelineStepLog.pipeline_run_id == pipeline_run_id,
                PipelineStepLog.tenant_id == user.tenant_id,
            )
            .order_by(PipelineStepLog.created_at.desc(), PipelineStepLog.id.desc())
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()
    data = [PipelineStepLogResponse.model_validate(row) for row in logs]
    if "limit" not in request.query_params and "offset" not in request.query_params:
        return data
    return Paginated[PipelineStepLogResponse](data=data, total=int(total), limit=limit, offset=offset)


@router.post("/trigger", response_model=TriggerPipelineResponse, status_code=status.HTTP_202_ACCEPTED)
async def trigger_pipeline_run(
    body: TriggerPipelineRequest,
    db: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> TriggerPipelineResponse:
    pipeline_run_id = await resolve_pipeline_run_id_for_trigger(
        session=db,
        tenant_id=user.tenant_id,
        sync_run_id=body.sync_run_id,
    )
    JobDispatcher().enqueue_task(
        trigger_post_sync_pipeline,
        tenant_id=str(user.tenant_id),
        sync_run_id=str(body.sync_run_id),
    )
    return TriggerPipelineResponse(
        pipeline_run_id=str(pipeline_run_id),
        status="queued",
    )
