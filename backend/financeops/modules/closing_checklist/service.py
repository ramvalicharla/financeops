from __future__ import annotations

import calendar
import hashlib
import json
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import NotFoundError, ValidationError
from financeops.core.intent.context import require_mutation_context
from financeops.core.intent.enums import IntentSourceChannel, IntentType
from financeops.core.intent.service import IntentActor, IntentService
from financeops.db.rls import clear_tenant_context, set_tenant_context
from financeops.db.session import AsyncSessionLocal
from financeops.modules.closing_checklist.models import (
    ChecklistRun,
    ChecklistRunTask,
    ChecklistTemplate,
    ChecklistTemplateTask,
)
from financeops.db.models.users import IamUser
from financeops.platform.db.models.entities import CpEntity


_DEFAULT_TEMPLATE_TASKS: list[dict[str, object]] = [
    {
        "task_name": "ERP data sync complete",
        "assigned_role": None,
        "days_relative": -3,
        "auto_trigger_event": "erp_sync_complete",
        "depends_on": [],
    },
    {
        "task_name": "GL/TB reconciliation",
        "assigned_role": None,
        "days_relative": -2,
        "auto_trigger_event": "recon_complete",
        "depends_on": [1],
    },
    {
        "task_name": "Intercompany reconciliation",
        "assigned_role": None,
        "days_relative": -2,
        "auto_trigger_event": None,
        "depends_on": [2],
    },
    {
        "task_name": "Payroll upload and reconciliation",
        "assigned_role": "data_entry_payroll",
        "days_relative": -1,
        "auto_trigger_event": None,
        "depends_on": [],
    },
    {
        "task_name": "Prepaid and accrual adjustments",
        "assigned_role": "manager",
        "days_relative": 0,
        "auto_trigger_event": None,
        "depends_on": [2],
    },
    {
        "task_name": "Fixed asset depreciation run",
        "assigned_role": None,
        "days_relative": 0,
        "auto_trigger_event": None,
        "depends_on": [2],
    },
    {
        "task_name": "Multi-entity consolidation",
        "assigned_role": None,
        "days_relative": 1,
        "auto_trigger_event": "consolidation_complete",
        "depends_on": [3, 5, 6],
    },
    {
        "task_name": "FX rate confirmation",
        "assigned_role": None,
        "days_relative": 0,
        "auto_trigger_event": None,
        "depends_on": [],
    },
    {
        "task_name": "MIS review and approval",
        "assigned_role": "finance_leader",
        "days_relative": 2,
        "auto_trigger_event": None,
        "depends_on": [7],
    },
    {
        "task_name": "Anomaly detection review",
        "assigned_role": None,
        "days_relative": 2,
        "auto_trigger_event": "anomaly_detection_complete",
        "depends_on": [7],
    },
    {
        "task_name": "Board pack generation",
        "assigned_role": None,
        "days_relative": 3,
        "auto_trigger_event": "board_pack_generated",
        "depends_on": [9, 10],
    },
    {
        "task_name": "Finance Leader sign-off",
        "assigned_role": "finance_leader",
        "days_relative": 4,
        "auto_trigger_event": None,
        "depends_on": [11],
    },
]


class DependencyNotMetError(ValidationError):
    """Raised when checklist dependencies are not completed."""

    def __init__(self, blocking_task_name: str) -> None:
        super().__init__(f"Dependency not met. Complete '{blocking_task_name}' first.")
        self.blocking_task_name = blocking_task_name


def _parse_period(period: str) -> tuple[int, int]:
    parts = str(period).split("-")
    if len(parts) != 2:
        raise ValidationError("period must be in YYYY-MM format")
    try:
        year = int(parts[0])
        month = int(parts[1])
    except ValueError as exc:
        raise ValidationError("period must be in YYYY-MM format") from exc
    if month < 1 or month > 12:
        raise ValidationError("period month must be between 01 and 12")
    return year, month


def period_start_date(period: str) -> date:
    year, month = _parse_period(period)
    return date(year, month, 1)


def period_end_date(period: str) -> date:
    year, month = _parse_period(period)
    end_day = calendar.monthrange(year, month)[1]
    return date(year, month, end_day)


async def _get_default_template(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    created_by: uuid.UUID,
) -> ChecklistTemplate:
    row = (
        await session.execute(
            select(ChecklistTemplate)
            .where(
                ChecklistTemplate.tenant_id == tenant_id,
                ChecklistTemplate.is_default.is_(True),
            )
            .order_by(ChecklistTemplate.created_at.asc(), ChecklistTemplate.id.asc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if row is None:
        require_mutation_context("Closing-checklist default template creation")
        template = ChecklistTemplate(
            tenant_id=tenant_id,
            name="Default Month-End Close Checklist",
            description="System default 12-step close checklist",
            is_default=True,
            created_by=created_by,
        )
        session.add(template)
        await session.flush()

        task_ids: list[uuid.UUID] = [uuid.uuid4() for _ in _DEFAULT_TEMPLATE_TASKS]
        for idx, task_spec in enumerate(_DEFAULT_TEMPLATE_TASKS, start=1):
            depends_idx = [int(value) for value in list(task_spec["depends_on"])]
            depends_on_ids = [str(task_ids[item - 1]) for item in depends_idx]
            session.add(
                ChecklistTemplateTask(
                    id=task_ids[idx - 1],
                    template_id=template.id,
                    tenant_id=tenant_id,
                    task_name=str(task_spec["task_name"]),
                    assigned_role=task_spec["assigned_role"],
                    days_relative_to_period_end=int(task_spec["days_relative"]),
                    depends_on_task_ids=depends_on_ids,
                    auto_trigger_event=task_spec["auto_trigger_event"],
                    order_index=idx,
                )
            )
        await session.flush()
        row = template
    return row


async def create_template(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    name: str,
    description: str | None,
    is_default: bool,
    created_by: uuid.UUID,
    tasks: list[dict[str, object]],
) -> ChecklistTemplate:
    require_mutation_context("Closing-checklist template creation")
    template = ChecklistTemplate(
        tenant_id=tenant_id,
        name=name,
        description=description,
        is_default=is_default,
        created_by=created_by,
    )
    session.add(template)
    await session.flush()

    for raw_task in tasks:
        session.add(
            ChecklistTemplateTask(
                template_id=template.id,
                tenant_id=tenant_id,
                task_name=str(raw_task["task_name"]),
                description=str(raw_task["description"]) if raw_task.get("description") not in {None, ""} else None,
                assigned_role=str(raw_task["assigned_role"]) if raw_task.get("assigned_role") not in {None, ""} else None,
                days_relative_to_period_end=int(raw_task["days_relative_to_period_end"]),
                depends_on_task_ids=[str(item) for item in list(raw_task.get("depends_on_task_ids") or [])],
                auto_trigger_event=(
                    str(raw_task["auto_trigger_event"]) if raw_task.get("auto_trigger_event") not in {None, ""} else None
                ),
                order_index=int(raw_task.get("order_index") or 0),
            )
        )
    await session.flush()
    return template


async def _recompute_run_status(session: AsyncSession, run: ChecklistRun) -> None:
    tasks = (
        await session.execute(
            select(ChecklistRunTask).where(ChecklistRunTask.run_id == run.id)
        )
    ).scalars().all()
    progress = await compute_progress(list(tasks))
    run.progress_pct = progress

    statuses = {task.status for task in tasks}
    if tasks and all(status in {"completed", "skipped"} for status in statuses):
        run.status = "completed"
        run.actual_close_date = date.today()
    elif "in_progress" in statuses:
        run.status = "in_progress"
        run.actual_close_date = None
    else:
        run.status = "open"
        run.actual_close_date = None


async def _resolve_entity_id(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID | None,
) -> uuid.UUID:
    if entity_id is not None:
        exists = (
            await session.execute(
                select(CpEntity.id).where(
                    CpEntity.id == entity_id,
                    CpEntity.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if exists is None:
            raise ValidationError("Entity not found")
        return entity_id

    default_entity_id = (
        await session.execute(
            select(CpEntity.id)
            .where(
                CpEntity.tenant_id == tenant_id,
                CpEntity.status == "active",
            )
            .order_by(CpEntity.created_at.asc(), CpEntity.id.asc())
        )
    ).scalars().first()
    if default_entity_id is None:
        default_entity_id = (
            await session.execute(
                select(CpEntity.id)
                .where(CpEntity.status == "active")
                .order_by(CpEntity.created_at.asc(), CpEntity.id.asc())
            )
        ).scalars().first()
    if default_entity_id is None:
        raise ValidationError("No active entity found for tenant")
    return default_entity_id


async def get_or_create_run(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    period: str,
    created_by: uuid.UUID,
    entity_id: uuid.UUID | None = None,
) -> ChecklistRun:
    """
    Get existing run for tenant+period or create from default template.
    Idempotent — calling twice returns same run.
    When creating: instantiate checklist_run_tasks from template tasks.
    Compute due_date for each task from period + days_relative.
    """
    _parse_period(period)
    resolved_entity_id = await _resolve_entity_id(session, tenant_id, entity_id)
    existing = (
        await session.execute(
            select(ChecklistRun).where(
                ChecklistRun.tenant_id == tenant_id,
                ChecklistRun.entity_id == resolved_entity_id,
                ChecklistRun.period == period,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    require_mutation_context("Closing-checklist run creation")

    template = await _get_default_template(
        session,
        tenant_id=tenant_id,
        created_by=created_by,
    )
    template_tasks = (
        await session.execute(
            select(ChecklistTemplateTask)
            .where(
                ChecklistTemplateTask.tenant_id == tenant_id,
                ChecklistTemplateTask.template_id == template.id,
            )
            .order_by(ChecklistTemplateTask.order_index.asc(), ChecklistTemplateTask.created_at.asc())
        )
    ).scalars().all()

    target_date = period_end_date(period) + timedelta(days=4)
    run = ChecklistRun(
        tenant_id=tenant_id,
        entity_id=resolved_entity_id,
        template_id=template.id,
        period=period,
        status="open",
        progress_pct=Decimal("0.00"),
        target_close_date=target_date,
        actual_close_date=None,
        created_by=created_by,
    )
    session.add(run)
    await session.flush()

    period_end = period_end_date(period)
    for template_task in template_tasks:
        due_date = period_end + timedelta(days=int(template_task.days_relative_to_period_end))
        run_task = ChecklistRunTask(
            run_id=run.id,
            template_task_id=template_task.id,
            tenant_id=tenant_id,
            entity_id=resolved_entity_id,
            task_name=template_task.task_name,
            assigned_role=template_task.assigned_role,
            due_date=due_date,
            status="not_started",
            order_index=template_task.order_index,
            is_auto_completed=False,
        )
        session.add(run_task)

    await session.flush()
    await _recompute_run_status(session, run)
    await session.flush()
    return run


async def _resolve_blocking_dependency(
    session: AsyncSession,
    *,
    run_id: uuid.UUID,
    template_task: ChecklistTemplateTask,
) -> str | None:
    depends = list(template_task.depends_on_task_ids or [])
    if not depends:
        return None
    dependency_ids: list[uuid.UUID] = []
    for raw in depends:
        try:
            dependency_ids.append(uuid.UUID(str(raw)))
        except ValueError:
            continue
    if not dependency_ids:
        return None

    dependency_rows = (
        await session.execute(
            select(ChecklistRunTask)
            .where(
                ChecklistRunTask.run_id == run_id,
                ChecklistRunTask.template_task_id.in_(dependency_ids),
            )
            .order_by(ChecklistRunTask.order_index.asc(), ChecklistRunTask.created_at.asc())
        )
    ).scalars().all()

    for row in dependency_rows:
        if row.status not in {"completed", "skipped"}:
            return row.task_name
    return None


async def update_task_status(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    run_id: uuid.UUID,
    task_id: uuid.UUID,
    new_status: str,
    updated_by: uuid.UUID,
    notes: str | None = None,
    entity_id: uuid.UUID | None = None,
) -> ChecklistRunTask:
    """
    Update a task's status.
    Validate: if task has depends_on, all dependencies must be
    'completed' before this task can be set to 'completed'.
    If dependency not met: raise DependencyNotMetError (HTTP 422).
    After update: recompute progress_pct on the run.
    If all tasks completed: set run.status = 'completed',
    run.actual_close_date = today().
    If any task moves to in_progress: set run.status = 'in_progress'.
    """
    require_mutation_context("Closing-checklist task status update")
    status_value = str(new_status or "").strip().lower()
    if status_value not in {"not_started", "in_progress", "completed", "blocked", "skipped"}:
        raise ValidationError("Invalid checklist task status")

    run = (
        await session.execute(
            select(ChecklistRun).where(
                ChecklistRun.id == run_id,
                ChecklistRun.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if run is None:
        raise NotFoundError("Checklist run not found")
    resolved_entity_id = await _resolve_entity_id(session, tenant_id, entity_id or run.entity_id)
    if run.entity_id != resolved_entity_id:
        raise NotFoundError("Checklist run not found")

    task = (
        await session.execute(
            select(ChecklistRunTask).where(
                ChecklistRunTask.id == task_id,
                ChecklistRunTask.run_id == run_id,
                ChecklistRunTask.tenant_id == tenant_id,
                ChecklistRunTask.entity_id == resolved_entity_id,
            )
        )
    ).scalar_one_or_none()
    if task is None:
        raise NotFoundError("Checklist task not found")

    template_task = (
        await session.execute(
            select(ChecklistTemplateTask).where(
                ChecklistTemplateTask.id == task.template_task_id,
                ChecklistTemplateTask.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if template_task is None:
        raise NotFoundError("Checklist template task not found")

    if status_value == "completed":
        blocker = await _resolve_blocking_dependency(session, run_id=run_id, template_task=template_task)
        if blocker is not None:
            raise DependencyNotMetError(blocker)

    now = datetime.now(UTC)
    task.status = status_value
    task.notes = notes
    task.updated_at = now
    if status_value in {"completed", "skipped"}:
        task.completed_at = now
        task.completed_by = updated_by
    else:
        task.completed_at = None
        task.completed_by = None

    await session.flush()
    await _recompute_run_status(session, run)
    await session.flush()
    return task


async def assign_task_to_user(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    run_id: uuid.UUID,
    task_id: uuid.UUID,
    assignee_id: uuid.UUID,
    entity_id: uuid.UUID | None = None,
) -> ChecklistRunTask:
    require_mutation_context("Closing-checklist task assignment")
    run = (
        await session.execute(
            select(ChecklistRun).where(
                ChecklistRun.id == run_id,
                ChecklistRun.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if run is None:
        raise NotFoundError("Checklist run not found")
    resolved_entity_id = await _resolve_entity_id(session, tenant_id, entity_id or run.entity_id)
    if run.entity_id != resolved_entity_id:
        raise NotFoundError("Checklist run not found")

    task = (
        await session.execute(
            select(ChecklistRunTask).where(
                ChecklistRunTask.id == task_id,
                ChecklistRunTask.run_id == run.id,
                ChecklistRunTask.tenant_id == tenant_id,
                ChecklistRunTask.entity_id == resolved_entity_id,
            )
        )
    ).scalar_one_or_none()
    if task is None:
        raise NotFoundError("Checklist task not found")

    assignee = (
        await session.execute(
            select(IamUser).where(
                IamUser.id == assignee_id,
                IamUser.tenant_id == tenant_id,
                IamUser.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if assignee is None:
        raise NotFoundError("Assignee not found")

    task.assigned_to = assignee.id
    task.updated_at = datetime.now(UTC)
    await session.flush()
    return task


async def auto_complete_task(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    period: str,
    event: str,
) -> list[ChecklistRunTask]:
    """
    Called when platform events fire.
    Finds the run for tenant+period, finds all run_tasks where
    the template_task has auto_trigger_event == event.
    Marks each as completed, is_auto_completed=True,
    auto_completed_by_event=event.
    Recomputes run progress_pct.
    Returns list of auto-completed tasks.
    If no run exists for the period: no-op (do not create).
    """
    require_mutation_context("Closing-checklist task auto-complete")
    run = (
        await session.execute(
            select(ChecklistRun).where(
                ChecklistRun.tenant_id == tenant_id,
                ChecklistRun.period == period,
            )
        )
    ).scalar_one_or_none()
    if run is None:
        return []

    rows = (
        await session.execute(
            select(ChecklistRunTask, ChecklistTemplateTask)
            .join(
                ChecklistTemplateTask,
                ChecklistTemplateTask.id == ChecklistRunTask.template_task_id,
            )
            .where(
                ChecklistRunTask.tenant_id == tenant_id,
                ChecklistRunTask.run_id == run.id,
                ChecklistTemplateTask.auto_trigger_event == event,
            )
            .order_by(ChecklistRunTask.order_index.asc(), ChecklistRunTask.created_at.asc())
        )
    ).all()

    completed: list[ChecklistRunTask] = []
    now = datetime.now(UTC)
    for run_task, template_task in rows:
        blocker = await _resolve_blocking_dependency(
            session,
            run_id=run.id,
            template_task=template_task,
        )
        if blocker is not None:
            continue
        if run_task.status in {"completed", "skipped"}:
            continue
        run_task.status = "completed"
        run_task.completed_at = now
        run_task.completed_by = None
        run_task.is_auto_completed = True
        run_task.auto_completed_by_event = event
        run_task.updated_at = now
        completed.append(run_task)

    if completed:
        await session.flush()
    await _recompute_run_status(session, run)
    await session.flush()
    return completed


async def compute_progress(
    run_tasks: list[ChecklistRunTask],
) -> Decimal:
    """
    completed_count / total_count * 100.
    Returns Decimal between 0 and 100.
    Skipped tasks count as completed for progress purposes.
    """
    if not run_tasks:
        return Decimal("0.00")
    total = Decimal(str(len(run_tasks)))
    completed_count = Decimal(
        str(sum(1 for task in run_tasks if task.status in {"completed", "skipped"}))
    )
    pct = (completed_count / total) * Decimal("100")
    return pct.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


async def get_closing_analytics(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID | None = None,
) -> dict:
    """
    Returns:
    - avg_days_to_close (last 12 completed runs)
    - fastest_close_period
    - slowest_close_period
    - on_time_rate (% completed by target_close_date)
    - most_blocked_task (task name that is blocked most often)
    - trend: 'improving' | 'stable' | 'worsening'
    All numeric values: Decimal not float.
    """
    resolved_entity_id = await _resolve_entity_id(session, tenant_id, entity_id)
    completed_runs = (
        await session.execute(
            select(ChecklistRun)
            .where(
                ChecklistRun.tenant_id == tenant_id,
                ChecklistRun.entity_id == resolved_entity_id,
                ChecklistRun.status == "completed",
                ChecklistRun.actual_close_date.is_not(None),
            )
            .order_by(ChecklistRun.period.desc(), ChecklistRun.created_at.desc())
            .limit(12)
        )
    ).scalars().all()

    days_to_close: list[tuple[str, Decimal]] = []
    on_time_count = 0
    for run in completed_runs:
        end_date = period_end_date(run.period)
        delta_days = Decimal(str((run.actual_close_date - end_date).days)) if run.actual_close_date else Decimal("0")
        days_to_close.append((run.period, delta_days))
        if run.target_close_date and run.actual_close_date and run.actual_close_date <= run.target_close_date:
            on_time_count += 1

    if days_to_close:
        avg_days_to_close = (
            sum((value for _, value in days_to_close), start=Decimal("0")) / Decimal(str(len(days_to_close)))
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        fastest_close_period = min(days_to_close, key=lambda item: item[1])[0]
        slowest_close_period = max(days_to_close, key=lambda item: item[1])[0]
        on_time_rate = (
            Decimal(str(on_time_count))
            / Decimal(str(len(days_to_close)))
            * Decimal("100")
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    else:
        avg_days_to_close = Decimal("0.00")
        fastest_close_period = None
        slowest_close_period = None
        on_time_rate = Decimal("0.00")

    blocked_row = (
        await session.execute(
            select(ChecklistRunTask.task_name, func.count(ChecklistRunTask.id).label("blocked_count"))
            .where(
                ChecklistRunTask.tenant_id == tenant_id,
                ChecklistRunTask.entity_id == resolved_entity_id,
                ChecklistRunTask.status == "blocked",
            )
            .group_by(ChecklistRunTask.task_name)
            .order_by(func.count(ChecklistRunTask.id).desc(), ChecklistRunTask.task_name.asc())
            .limit(1)
        )
    ).first()
    most_blocked_task = blocked_row[0] if blocked_row else None

    trend = "stable"
    if len(days_to_close) >= 6:
        recent = [value for _, value in days_to_close[:3]]
        older = [value for _, value in days_to_close[3:6]]
        recent_avg = sum(recent, start=Decimal("0")) / Decimal(str(len(recent)))
        older_avg = sum(older, start=Decimal("0")) / Decimal(str(len(older)))
        if recent_avg < older_avg - Decimal("0.25"):
            trend = "improving"
        elif recent_avg > older_avg + Decimal("0.25"):
            trend = "worsening"

    return {
        "avg_days_to_close": avg_days_to_close,
        "fastest_close_period": fastest_close_period,
        "slowest_close_period": slowest_close_period,
        "on_time_rate": on_time_rate,
        "most_blocked_task": most_blocked_task,
        "trend": trend,
    }


async def run_auto_complete_for_event(
    *,
    tenant_id: uuid.UUID | str,
    period: str,
    event: str,
) -> None:
    """Run checklist auto-completion in an isolated background DB session."""
    parsed_tenant_id = uuid.UUID(str(tenant_id))
    async with AsyncSessionLocal() as session:
        try:
            await set_tenant_context(session, parsed_tenant_id)
            raw = json.dumps(
                {
                    "tenant_id": str(parsed_tenant_id),
                    "period": period,
                    "event": event,
                    "intent_type": IntentType.AUTO_COMPLETE_CHECKLIST_TASKS.value,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            await IntentService(session).submit_intent(
                intent_type=IntentType.AUTO_COMPLETE_CHECKLIST_TASKS,
                actor=IntentActor(
                    user_id=uuid.uuid5(parsed_tenant_id, f"closing-checklist:{period}:{event}"),
                    tenant_id=parsed_tenant_id,
                    role="finance_leader",
                    source_channel=IntentSourceChannel.SYSTEM.value,
                    correlation_id=f"closing-checklist:{period}:{event}",
                ),
                payload={"period": period, "event": event},
                idempotency_key=hashlib.sha256(raw.encode("utf-8")).hexdigest(),
            )
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await clear_tenant_context(session)

