from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user, require_finance_leader
from financeops.db.models.users import IamUser, UserRole
from financeops.modules.closing_checklist.models import (
    ChecklistRun,
    ChecklistRunTask,
    ChecklistTemplate,
    ChecklistTemplateTask,
)
from financeops.modules.closing_checklist.service import (
    DependencyNotMetError,
    get_closing_analytics,
    get_or_create_run,
    period_end_date,
    period_start_date,
    update_task_status,
)
from financeops.modules.accounting_layer.application.governance_service import (
    complete_checklist_item,
    ensure_unlock_role,
    get_close_checklist,
    get_period_status,
    lock_period,
    run_close_readiness,
    unlock_period,
)
from financeops.modules.notifications.service import send_notification
from financeops.platform.services.tenancy.entity_access import assert_entity_access, get_entities_for_user
from financeops.shared_kernel.pagination import Paginated

router = APIRouter(prefix="/close", tags=["closing-checklist"])


class TaskStatusPatchRequest(BaseModel):
    status: str
    notes: str | None = None


class TaskAssignRequest(BaseModel):
    user_id: uuid.UUID


class TemplateTaskRequest(BaseModel):
    task_name: str
    description: str | None = None
    assigned_role: str | None = None
    days_relative_to_period_end: int
    depends_on_task_ids: list[uuid.UUID] = Field(default_factory=list)
    auto_trigger_event: str | None = None
    order_index: int = 0


class CreateTemplateRequest(BaseModel):
    name: str
    description: str | None = None
    is_default: bool = False
    tasks: list[TemplateTaskRequest]


class ChecklistTemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    description: str | None
    is_default: bool
    created_by: uuid.UUID
    created_at: date | None
    updated_at: date | None


class LockPeriodRequest(BaseModel):
    org_entity_id: uuid.UUID | None = None
    fiscal_year: int = Field(..., ge=2000, le=2100)
    period_number: int = Field(..., ge=1, le=12)
    lock_type: str
    reason: str | None = None


class UnlockPeriodRequest(BaseModel):
    org_entity_id: uuid.UUID | None = None
    fiscal_year: int = Field(..., ge=2000, le=2100)
    period_number: int = Field(..., ge=1, le=12)
    reason: str


class CompleteChecklistItemRequest(BaseModel):
    org_entity_id: uuid.UUID
    fiscal_year: int = Field(..., ge=2000, le=2100)
    period_number: int = Field(..., ge=1, le=12)
    checklist_type: str
    evidence_json: dict[str, object] | None = None


class ReadinessRequest(BaseModel):
    org_entity_id: uuid.UUID
    fiscal_year: int = Field(..., ge=2000, le=2100)
    period_number: int = Field(..., ge=1, le=12)


_ROLE_MAP: dict[str, set[str]] = {
    "finance_leader": {UserRole.finance_leader.value, UserRole.super_admin.value},
    "manager": {
        UserRole.finance_team.value,
        UserRole.finance_leader.value,
        UserRole.super_admin.value,
    },
    "reviewer": {
        UserRole.read_only.value,
        UserRole.auditor.value,
        UserRole.finance_team.value,
        UserRole.finance_leader.value,
        UserRole.super_admin.value,
    },
    "data_entry_gl": {
        UserRole.finance_team.value,
        UserRole.finance_leader.value,
        UserRole.super_admin.value,
    },
    "data_entry_payroll": {
        UserRole.finance_team.value,
        UserRole.finance_leader.value,
        UserRole.super_admin.value,
    },
}


def _ensure_period(period: str) -> str:
    try:
        start = period_start_date(period)
    except Exception as exc:
        raise HTTPException(status_code=422, detail="period must be YYYY-MM") from exc
    return f"{start.year:04d}-{start.month:02d}"


def _to_str(value: Decimal | None) -> str:
    if value is None:
        return "0"
    return format(value, "f")


def _can_lock_period(user: IamUser) -> bool:
    return user.role in {
        UserRole.finance_leader,
        UserRole.super_admin,
        UserRole.platform_owner,
        UserRole.platform_admin,
    }


async def _load_run_by_period(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    period: str,
) -> ChecklistRun | None:
    return (
        await session.execute(
            select(ChecklistRun).where(
                ChecklistRun.tenant_id == tenant_id,
                ChecklistRun.entity_id == entity_id,
                ChecklistRun.period == period,
            )
        )
    ).scalar_one_or_none()


async def _load_tasks_with_templates(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    run_id: uuid.UUID,
) -> tuple[list[ChecklistRunTask], dict[uuid.UUID, ChecklistTemplateTask]]:
    tasks = (
        await session.execute(
            select(ChecklistRunTask)
            .where(
                ChecklistRunTask.tenant_id == tenant_id,
                ChecklistRunTask.entity_id == entity_id,
                ChecklistRunTask.run_id == run_id,
            )
            .order_by(ChecklistRunTask.order_index.asc(), ChecklistRunTask.created_at.asc())
        )
    ).scalars().all()
    template_ids = [task.template_task_id for task in tasks]
    template_rows = (
        await session.execute(
            select(ChecklistTemplateTask).where(
                ChecklistTemplateTask.tenant_id == tenant_id,
                ChecklistTemplateTask.id.in_(template_ids),
            )
        )
    ).scalars().all()
    template_map = {row.id: row for row in template_rows}
    return list(tasks), template_map


def _dependency_met(
    *,
    task: ChecklistRunTask,
    tasks_by_template_id: dict[uuid.UUID, ChecklistRunTask],
    template_task: ChecklistTemplateTask | None,
) -> bool:
    if template_task is None:
        return True
    depends = list(template_task.depends_on_task_ids or [])
    for dep in depends:
        try:
            dep_id = uuid.UUID(str(dep))
        except ValueError:
            continue
        dep_task = tasks_by_template_id.get(dep_id)
        if dep_task is None:
            continue
        if dep_task.status not in {"completed", "skipped"}:
            return False
    return True


def _serialize_task(
    task: ChecklistRunTask,
    *,
    template_task: ChecklistTemplateTask | None,
    dependency_met: bool,
) -> dict:
    return {
        "id": str(task.id),
        "run_id": str(task.run_id),
        "template_task_id": str(task.template_task_id),
        "task_name": task.task_name,
        "assigned_to": str(task.assigned_to) if task.assigned_to else None,
        "assigned_role": task.assigned_role,
        "due_date": task.due_date.isoformat() if task.due_date else None,
        "status": task.status,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "completed_by": str(task.completed_by) if task.completed_by else None,
        "notes": task.notes,
        "is_auto_completed": task.is_auto_completed,
        "auto_completed_by_event": task.auto_completed_by_event,
        "order_index": task.order_index,
        "dependency_met": dependency_met,
        "depends_on_task_ids": list((template_task.depends_on_task_ids if template_task else []) or []),
    }


def _can_update_task(user: IamUser, assigned_role: str | None) -> bool:
    if user.role in {UserRole.finance_leader, UserRole.super_admin}:
        return True
    if not assigned_role:
        return True
    allowed = _ROLE_MAP.get(assigned_role, {assigned_role})
    return user.role.value in allowed


async def _resolve_entity_for_user(
    session: AsyncSession,
    user: IamUser,
    entity_id: uuid.UUID | None,
) -> uuid.UUID:
    if entity_id is not None:
        await assert_entity_access(session, user.tenant_id, entity_id, user.id, user.role)
        return entity_id
    entities = await get_entities_for_user(
        session=session,
        tenant_id=user.tenant_id,
        user_id=user.id,
        user_role=user.role,
    )
    if not entities:
        raise HTTPException(
            status_code=422,
            detail="entity_id is required because no entity is configured for this user",
        )
    return entities[0].id


@router.post("/lock-period")
async def lock_period_endpoint(
    body: LockPeriodRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    if not _can_lock_period(user):
        raise HTTPException(status_code=403, detail="finance approver role required")

    if body.lock_type.upper() == "HARD_CLOSED":
        if body.org_entity_id is None:
            raise HTTPException(
                status_code=422,
                detail="org_entity_id is required for HARD_CLOSED lock.",
            )
        readiness = await run_close_readiness(
            session,
            tenant_id=user.tenant_id,
            org_entity_id=body.org_entity_id,
            fiscal_year=body.fiscal_year,
            period_number=body.period_number,
        )
        if not readiness["pass"]:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "READINESS_FAILED",
                    "message": "Cannot hard-close period with unresolved blockers.",
                    "blockers": readiness["blockers"],
                    "warnings": readiness["warnings"],
                },
            )

    payload = await lock_period(
        session,
        tenant_id=user.tenant_id,
        org_entity_id=body.org_entity_id,
        fiscal_year=body.fiscal_year,
        period_number=body.period_number,
        lock_type=body.lock_type,
        reason=body.reason,
        actor_user_id=user.id,
    )
    await session.flush()
    return payload


@router.post("/unlock-period")
async def unlock_period_endpoint(
    body: UnlockPeriodRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    ensure_unlock_role(user.role)
    payload = await unlock_period(
        session,
        tenant_id=user.tenant_id,
        org_entity_id=body.org_entity_id,
        fiscal_year=body.fiscal_year,
        period_number=body.period_number,
        reason=body.reason,
        actor_user_id=user.id,
    )
    await session.flush()
    return payload


@router.get("/period-status")
async def period_status_endpoint(
    fiscal_year: int = Query(..., ge=2000, le=2100),
    period_number: int = Query(..., ge=1, le=12),
    org_entity_id: uuid.UUID | None = Query(default=None),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    if org_entity_id is not None:
        await assert_entity_access(
            session,
            user.tenant_id,
            org_entity_id,
            user.id,
            user.role,
        )
    payload = await get_period_status(
        session,
        tenant_id=user.tenant_id,
        org_entity_id=org_entity_id,
        fiscal_year=fiscal_year,
        period_number=period_number,
    )
    return payload


@router.get("/checklist")
async def checklist_governance_endpoint(
    org_entity_id: uuid.UUID = Query(...),
    fiscal_year: int = Query(..., ge=2000, le=2100),
    period_number: int = Query(..., ge=1, le=12),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    await assert_entity_access(
        session,
        user.tenant_id,
        org_entity_id,
        user.id,
        user.role,
    )
    return await get_close_checklist(
        session,
        tenant_id=user.tenant_id,
        org_entity_id=org_entity_id,
        fiscal_year=fiscal_year,
        period_number=period_number,
    )


@router.post("/checklist/complete")
async def complete_checklist_item_endpoint(
    body: CompleteChecklistItemRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    await assert_entity_access(
        session,
        user.tenant_id,
        body.org_entity_id,
        user.id,
        user.role,
    )
    payload = await complete_checklist_item(
        session,
        tenant_id=user.tenant_id,
        org_entity_id=body.org_entity_id,
        fiscal_year=body.fiscal_year,
        period_number=body.period_number,
        checklist_type=body.checklist_type,
        evidence_json=body.evidence_json,
        actor_user_id=user.id,
    )
    await session.flush()
    return payload


@router.post("/run-readiness")
async def run_readiness_endpoint(
    body: ReadinessRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    await assert_entity_access(
        session,
        user.tenant_id,
        body.org_entity_id,
        user.id,
        user.role,
    )
    return await run_close_readiness(
        session,
        tenant_id=user.tenant_id,
        org_entity_id=body.org_entity_id,
        fiscal_year=body.fiscal_year,
        period_number=body.period_number,
    )


@router.get("/history")
async def list_history(
    entity_id: uuid.UUID | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int | None = Query(default=None, ge=0),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> Paginated[dict]:
    resolved_entity_id = await _resolve_entity_for_user(session, user, entity_id)
    effective_skip = offset if offset is not None else skip
    base_stmt = select(ChecklistRun).where(
        ChecklistRun.tenant_id == user.tenant_id,
        ChecklistRun.entity_id == resolved_entity_id,
    )
    total = (await session.execute(select(func.count()).select_from(base_stmt.subquery()))).scalar_one()
    rows = (
        await session.execute(
            base_stmt
            .order_by(ChecklistRun.period.desc(), ChecklistRun.created_at.desc())
            .limit(limit)
            .offset(effective_skip)
        )
    ).scalars().all()

    data: list[dict] = []
    for row in rows:
        days_to_close: int | None = None
        if row.actual_close_date is not None:
            days_to_close = (row.actual_close_date - period_end_date(row.period)).days
        data.append(
            {
                "id": str(row.id),
                "period": row.period,
                "status": row.status,
                "progress_pct": _to_str(row.progress_pct),
                "actual_close_date": row.actual_close_date.isoformat() if row.actual_close_date else None,
                "days_to_close": days_to_close,
            }
        )

    return Paginated[dict](items=data, total=int(total), limit=limit, skip=effective_skip, has_more=(effective_skip + len(data)) < int(total))


@router.get("/analytics")
async def get_analytics(
    entity_id: uuid.UUID | None = None,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    resolved_entity_id = await _resolve_entity_for_user(session, user, entity_id)
    analytics = await get_closing_analytics(session, user.tenant_id, resolved_entity_id)
    return {
        "avg_days_to_close": _to_str(analytics["avg_days_to_close"]),
        "fastest_close_period": analytics["fastest_close_period"],
        "slowest_close_period": analytics["slowest_close_period"],
        "on_time_rate": _to_str(analytics["on_time_rate"]),
        "most_blocked_task": analytics["most_blocked_task"],
        "trend": analytics["trend"],
    }


@router.post("/templates", status_code=status.HTTP_201_CREATED)
async def create_template(
    body: CreateTemplateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> dict:
    template = ChecklistTemplate(
        tenant_id=user.tenant_id,
        name=body.name,
        description=body.description,
        is_default=body.is_default,
        created_by=user.id,
    )
    session.add(template)
    await session.flush()

    for task in body.tasks:
        row = ChecklistTemplateTask(
            template_id=template.id,
            tenant_id=user.tenant_id,
            task_name=task.task_name,
            description=task.description,
            assigned_role=task.assigned_role,
            days_relative_to_period_end=task.days_relative_to_period_end,
            depends_on_task_ids=[str(item) for item in task.depends_on_task_ids],
            auto_trigger_event=task.auto_trigger_event,
            order_index=task.order_index,
        )
        session.add(row)

    await session.flush()
    return {
        "id": str(template.id),
        "name": template.name,
        "is_default": template.is_default,
    }


@router.get("/templates")
async def list_templates(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int | None = Query(default=None, ge=0),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> Paginated[dict]:
    effective_skip = offset if offset is not None else skip
    base_stmt = select(ChecklistTemplate).where(ChecklistTemplate.tenant_id == user.tenant_id)
    total = (await session.execute(select(func.count()).select_from(base_stmt.subquery()))).scalar_one()
    rows = (
        await session.execute(
            base_stmt
            .order_by(ChecklistTemplate.created_at.desc(), ChecklistTemplate.id.desc())
            .limit(limit)
            .offset(effective_skip)
        )
    ).scalars().all()
    return Paginated[dict](
        items=[
            {
                "id": str(row.id),
                "name": row.name,
                "description": row.description,
                "is_default": row.is_default,
            }
            for row in rows
        ],
        total=int(total),
        limit=limit,
        skip=effective_skip,
        has_more=(effective_skip + len(rows)) < int(total),
    )


@router.get("/{period}")
async def get_or_create_checklist(
    period: str,
    entity_id: uuid.UUID | None = None,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    resolved_entity_id = await _resolve_entity_for_user(session, user, entity_id)
    normalized_period = _ensure_period(period)
    run = await get_or_create_run(
        session,
        tenant_id=user.tenant_id,
        period=normalized_period,
        created_by=user.id,
        entity_id=resolved_entity_id,
    )
    await session.flush()

    tasks, template_map = await _load_tasks_with_templates(
        session,
        tenant_id=user.tenant_id,
        entity_id=resolved_entity_id,
        run_id=run.id,
    )
    tasks_by_template = {task.template_task_id: task for task in tasks}

    task_payload: list[dict] = []
    completed_count = 0
    for task in tasks:
        template_task = template_map.get(task.template_task_id)
        dependency_met = _dependency_met(
            task=task,
            tasks_by_template_id=tasks_by_template,
            template_task=template_task,
        )
        if task.status in {"completed", "skipped"}:
            completed_count += 1
        task_payload.append(
            _serialize_task(task, template_task=template_task, dependency_met=dependency_met)
        )

    today = date.today()
    period_end = period_end_date(normalized_period)
    return {
        "run": {
            "id": str(run.id),
            "period": run.period,
            "status": run.status,
            "progress_pct": _to_str(run.progress_pct),
            "target_close_date": run.target_close_date.isoformat() if run.target_close_date else None,
            "actual_close_date": run.actual_close_date.isoformat() if run.actual_close_date else None,
            "days_until_period_end": (period_end - today).days,
            "is_overdue": bool(run.target_close_date and run.target_close_date < today and run.status != "completed"),
            "completed_count": completed_count,
            "total_count": len(tasks),
        },
        "tasks": task_payload,
    }


@router.patch("/{period}/tasks/{task_id}")
async def patch_task_status(
    period: str,
    task_id: uuid.UUID,
    body: TaskStatusPatchRequest,
    entity_id: uuid.UUID | None = None,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    normalized_period = _ensure_period(period)
    resolved_entity_id: uuid.UUID
    if entity_id is not None:
        resolved_entity_id = await _resolve_entity_for_user(session, user, entity_id)
    else:
        run_for_period = (
            await session.execute(
                select(ChecklistRun).where(
                    ChecklistRun.tenant_id == user.tenant_id,
                    ChecklistRun.period == normalized_period,
                )
            )
        ).scalar_one_or_none()
        if run_for_period is not None:
            resolved_entity_id = run_for_period.entity_id
        else:
            resolved_entity_id = await _resolve_entity_for_user(session, user, None)
    await assert_entity_access(session, user.tenant_id, resolved_entity_id, user.id, user.role)
    run = await _load_run_by_period(
        session,
        tenant_id=user.tenant_id,
        entity_id=resolved_entity_id,
        period=normalized_period,
    )
    if run is None:
        raise HTTPException(status_code=404, detail="Checklist run not found")

    task = (
        await session.execute(
            select(ChecklistRunTask).where(
                ChecklistRunTask.id == task_id,
                ChecklistRunTask.run_id == run.id,
                ChecklistRunTask.tenant_id == user.tenant_id,
                ChecklistRunTask.entity_id == resolved_entity_id,
            )
        )
    ).scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Checklist task not found")

    if not _can_update_task(user, task.assigned_role):
        raise HTTPException(status_code=403, detail="Role is not allowed to update this task")

    try:
        updated = await update_task_status(
            session,
            tenant_id=user.tenant_id,
            run_id=run.id,
            task_id=task.id,
            new_status=body.status,
            updated_by=user.id,
            notes=body.notes,
            entity_id=resolved_entity_id,
        )
    except DependencyNotMetError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc

    await session.flush()
    refreshed_run = await _load_run_by_period(
        session,
        tenant_id=user.tenant_id,
        entity_id=resolved_entity_id,
        period=normalized_period,
    )
    return {
        "task": {
            "id": str(updated.id),
            "status": updated.status,
            "notes": updated.notes,
            "completed_at": updated.completed_at.isoformat() if updated.completed_at else None,
        },
        "run": {
            "id": str(refreshed_run.id) if refreshed_run else str(run.id),
            "status": refreshed_run.status if refreshed_run else run.status,
            "progress_pct": _to_str((refreshed_run.progress_pct if refreshed_run else run.progress_pct)),
        },
    }


@router.post("/{period}/tasks/{task_id}/assign")
async def assign_task(
    period: str,
    task_id: uuid.UUID,
    body: TaskAssignRequest,
    entity_id: uuid.UUID | None = None,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> dict:
    resolved_entity_id = await _resolve_entity_for_user(session, user, entity_id)
    normalized_period = _ensure_period(period)
    run = await _load_run_by_period(
        session,
        tenant_id=user.tenant_id,
        entity_id=resolved_entity_id,
        period=normalized_period,
    )
    if run is None:
        raise HTTPException(status_code=404, detail="Checklist run not found")

    task = (
        await session.execute(
            select(ChecklistRunTask).where(
                ChecklistRunTask.id == task_id,
                ChecklistRunTask.run_id == run.id,
                ChecklistRunTask.tenant_id == user.tenant_id,
                ChecklistRunTask.entity_id == resolved_entity_id,
            )
        )
    ).scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Checklist task not found")

    assignee = (
        await session.execute(
            select(IamUser).where(
                IamUser.id == body.user_id,
                IamUser.tenant_id == user.tenant_id,
                IamUser.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if assignee is None:
        raise HTTPException(status_code=404, detail="Assignee not found")

    task.assigned_to = assignee.id
    task.updated_at = datetime.now(UTC)
    await session.flush()
    try:
        await send_notification(
            session,
            tenant_id=user.tenant_id,
            recipient_user_id=assignee.id,
            notification_type="task_assigned",
            title=f"Task assigned: {task.task_name}",
            body="You have been assigned a closing checklist task.",
            action_url=f"/close/{normalized_period}",
            metadata={"task_id": str(task.id), "period": normalized_period},
        )
    except Exception:
        pass

    return {
        "task_id": str(task.id),
        "assigned_to": str(task.assigned_to),
    }

