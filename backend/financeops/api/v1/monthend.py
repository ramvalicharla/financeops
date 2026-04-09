from __future__ import annotations

import logging
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import (
    get_async_session,
    get_current_user,
    require_finance_leader,
    require_finance_team,
)
from financeops.core.intent.api import build_idempotency_key, build_intent_actor
from financeops.core.intent.enums import IntentType
from financeops.core.intent.service import IntentService
from financeops.db.models.monthend import MonthEndChecklist, MonthEndTask
from financeops.db.models.users import IamUser
from financeops.services.monthend_service import (
    get_checklist,
    list_checklists,
    list_tasks,
)

log = logging.getLogger(__name__)
router = APIRouter()


async def _submit_intent(
    request: Request,
    session: AsyncSession,
    *,
    user: IamUser,
    intent_type: IntentType,
    payload: dict,
):
    return await IntentService(session).submit_intent(
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


class CreateChecklistRequest(BaseModel):
    period_year: int
    period_month: int
    entity_name: str
    notes: str | None = None
    add_default_tasks: bool = True


class AddTaskRequest(BaseModel):
    task_name: str
    task_category: str = "other"
    priority: str = "medium"
    sort_order: int = 0
    description: str | None = None
    assigned_to: UUID | None = None
    due_date: date | None = None
    is_required: bool = True


class UpdateTaskStatusRequest(BaseModel):
    status: str
    notes: str | None = None


class CloseChecklistRequest(BaseModel):
    notes: str | None = None


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_monthend_checklist(
    request: Request,
    body: CreateChecklistRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict:
    result = await _submit_intent(
        request,
        session,
        user=user,
        intent_type=IntentType.CREATE_MONTHEND_CHECKLIST,
        payload=body.model_dump(mode="json"),
    )
    checklist = await session.get(MonthEndChecklist, UUID(str((result.record_refs or {})["checklist_id"])))
    return {
        "checklist_id": str(checklist.id),
        "period_year": checklist.period_year,
        "period_month": checklist.period_month,
        "entity_name": checklist.entity_name,
        "status": checklist.status,
        "created_at": checklist.created_at.isoformat(),
        "intent_id": str(result.intent_id),
        "job_id": str(result.job_id) if result.job_id else None,
    }


@router.get("/")
async def list_monthend_checklists(
    entity_name: str | None = None,
    checklist_status: str | None = None,
    limit: int = 24,
    offset: int = 0,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    checklists = await list_checklists(
        session,
        tenant_id=user.tenant_id,
        entity_name=entity_name,
        status=checklist_status,
        limit=limit,
        offset=offset,
    )
    return {
        "checklists": [
            {
                "checklist_id": str(c.id),
                "period_year": c.period_year,
                "period_month": c.period_month,
                "entity_name": c.entity_name,
                "status": c.status,
                "created_at": c.created_at.isoformat(),
            }
            for c in checklists
        ],
        "count": len(checklists),
    }


@router.get("/{checklist_id}")
async def get_monthend_checklist(
    checklist_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    checklist = await get_checklist(session, user.tenant_id, checklist_id)
    if checklist is None:
        raise HTTPException(status_code=404, detail="Checklist not found")
    tasks = await list_tasks(session, user.tenant_id, checklist_id)
    return {
        "checklist_id": str(checklist.id),
        "period_year": checklist.period_year,
        "period_month": checklist.period_month,
        "entity_name": checklist.entity_name,
        "status": checklist.status,
        "closed_at": checklist.closed_at.isoformat() if checklist.closed_at else None,
        "tasks": [
            {
                "task_id": str(t.id),
                "task_name": t.task_name,
                "task_category": t.task_category,
                "priority": t.priority,
                "status": t.status,
                "assigned_to": str(t.assigned_to) if t.assigned_to else None,
                "sort_order": t.sort_order,
                "is_required": t.is_required,
                "completed_at": t.completed_at.isoformat() if t.completed_at else None,
            }
            for t in tasks
        ],
        "created_at": checklist.created_at.isoformat(),
    }


@router.post("/{checklist_id}/tasks", status_code=status.HTTP_201_CREATED)
async def add_checklist_task(
    request: Request,
    checklist_id: UUID,
    body: AddTaskRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict:
    result = await _submit_intent(
        request,
        session,
        user=user,
        intent_type=IntentType.ADD_MONTHEND_TASK,
        payload={"checklist_id": str(checklist_id), **body.model_dump(mode="json")},
    )
    task = await session.get(MonthEndTask, UUID(str((result.record_refs or {})["task_id"])))
    return {
        "task_id": str(task.id),
        "task_name": task.task_name,
        "status": task.status,
        "priority": task.priority,
        "intent_id": str(result.intent_id),
        "job_id": str(result.job_id) if result.job_id else None,
    }


@router.patch("/{checklist_id}/tasks/{task_id}")
async def update_task(
    request: Request,
    checklist_id: UUID,
    task_id: UUID,
    body: UpdateTaskStatusRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict:
    result = await _submit_intent(
        request,
        session,
        user=user,
        intent_type=IntentType.UPDATE_MONTHEND_TASK_STATUS,
        payload={
            "checklist_id": str(checklist_id),
            "task_id": str(task_id),
            "status": body.status,
            "notes": body.notes,
        },
    )
    task = await session.get(MonthEndTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return {
        "task_id": str(task.id),
        "task_name": task.task_name,
        "status": task.status,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "intent_id": str(result.intent_id),
        "job_id": str(result.job_id) if result.job_id else None,
    }


@router.post("/{checklist_id}/close", status_code=status.HTTP_201_CREATED)
async def close_monthend_checklist(
    request: Request,
    checklist_id: UUID,
    body: CloseChecklistRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> dict:
    result = await _submit_intent(
        request,
        session,
        user=user,
        intent_type=IntentType.CLOSE_MONTHEND_CHECKLIST,
        payload={"checklist_id": str(checklist_id), **body.model_dump(mode="json")},
    )
    closed = await session.get(MonthEndChecklist, UUID(str((result.record_refs or {})["checklist_id"])))
    if closed is None:
        raise HTTPException(status_code=404, detail="Checklist not found")
    return {
        "checklist_id": str(closed.id),
        "status": closed.status,
        "closed_at": closed.closed_at.isoformat() if closed.closed_at else None,
        "intent_id": str(result.intent_id),
        "job_id": str(result.job_id) if result.job_id else None,
    }
