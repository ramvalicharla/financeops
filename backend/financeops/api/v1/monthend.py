from __future__ import annotations

import logging
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import (
    get_async_session,
    get_current_user,
    require_finance_leader,
    require_finance_team,
)
from financeops.db.models.users import IamUser
from financeops.services.monthend_service import (
    add_task,
    close_checklist,
    create_checklist,
    get_checklist,
    list_checklists,
    list_tasks,
    update_task_status,
)

log = logging.getLogger(__name__)
router = APIRouter()


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
    status: str  # pending / in_progress / completed / skipped
    notes: str | None = None


class CloseChecklistRequest(BaseModel):
    notes: str | None = None


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_monthend_checklist(
    body: CreateChecklistRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict:
    """Create a month-end closing checklist (INSERT ONLY)."""
    checklist = await create_checklist(
        session,
        tenant_id=user.tenant_id,
        period_year=body.period_year,
        period_month=body.period_month,
        entity_name=body.entity_name,
        created_by=user.id,
        notes=body.notes,
        add_default_tasks=body.add_default_tasks,
    )
    await session.commit()
    return {
        "checklist_id": str(checklist.id),
        "period_year": checklist.period_year,
        "period_month": checklist.period_month,
        "entity_name": checklist.entity_name,
        "status": checklist.status,
        "created_at": checklist.created_at.isoformat(),
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
    """List month-end checklists."""
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
    """Get a checklist with all its tasks."""
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
    checklist_id: UUID,
    body: AddTaskRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict:
    """Add a task to a checklist."""
    task = await add_task(
        session,
        tenant_id=user.tenant_id,
        checklist_id=checklist_id,
        task_name=body.task_name,
        task_category=body.task_category,
        priority=body.priority,
        sort_order=body.sort_order,
        description=body.description,
        assigned_to=body.assigned_to,
        due_date=body.due_date,
        is_required=body.is_required,
    )
    await session.commit()
    return {
        "task_id": str(task.id),
        "task_name": task.task_name,
        "status": task.status,
        "priority": task.priority,
    }


@router.patch("/{checklist_id}/tasks/{task_id}")
async def update_task(
    checklist_id: UUID,
    task_id: UUID,
    body: UpdateTaskStatusRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict:
    """Update task status."""
    task = await update_task_status(
        session,
        tenant_id=user.tenant_id,
        task_id=task_id,
        status=body.status,
        completed_by=user.id if body.status == "completed" else None,
        notes=body.notes,
    )
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    await session.commit()
    return {
        "task_id": str(task.id),
        "task_name": task.task_name,
        "status": task.status,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
    }


@router.post("/{checklist_id}/close", status_code=status.HTTP_201_CREATED)
async def close_monthend_checklist(
    checklist_id: UUID,
    body: CloseChecklistRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> dict:
    """Close a month-end checklist (creates new closed record — INSERT ONLY)."""
    closed = await close_checklist(
        session,
        tenant_id=user.tenant_id,
        checklist_id=checklist_id,
        closed_by=user.id,
        notes=body.notes,
    )
    if closed is None:
        raise HTTPException(status_code=404, detail="Checklist not found")
    await session.commit()
    return {
        "checklist_id": str(closed.id),
        "status": closed.status,
        "closed_at": closed.closed_at.isoformat() if closed.closed_at else None,
    }
