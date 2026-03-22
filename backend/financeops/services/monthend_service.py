from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.monthend import MonthEndChecklist, MonthEndTask
from financeops.utils.chain_hash import compute_chain_hash, get_previous_hash_locked

log = logging.getLogger(__name__)

DEFAULT_TASKS = [
    {"name": "Upload Trial Balance", "category": "reconciliation", "priority": "high", "sort_order": 1},
    {"name": "Upload GL Entries", "category": "reconciliation", "priority": "high", "sort_order": 2},
    {"name": "Run GL/TB Reconciliation", "category": "reconciliation", "priority": "high", "sort_order": 3},
    {"name": "Upload Bank Statements", "category": "reconciliation", "priority": "high", "sort_order": 4},
    {"name": "Run Bank Reconciliation", "category": "reconciliation", "priority": "high", "sort_order": 5},
    {"name": "Intercompany Confirmation", "category": "approval", "priority": "medium", "sort_order": 6},
    {"name": "Prepaid Schedule Review", "category": "reconciliation", "priority": "medium", "sort_order": 7},
    {"name": "Accruals and Provisions", "category": "approval", "priority": "high", "sort_order": 8},
    {"name": "Finance Leader Review", "category": "approval", "priority": "high", "sort_order": 9},
    {"name": "Final Approval & Lock", "category": "approval", "priority": "high", "sort_order": 10},
]


async def create_checklist(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    period_year: int,
    period_month: int,
    entity_name: str,
    created_by: uuid.UUID,
    notes: str | None = None,
    add_default_tasks: bool = True,
) -> MonthEndChecklist:
    """
    Create a month-end closing checklist for a period/entity (INSERT ONLY).
    Optionally adds a standard set of default tasks.
    """
    previous_hash = await get_previous_hash_locked(session, MonthEndChecklist, tenant_id)
    record_data = {
        "tenant_id": str(tenant_id),
        "period_year": period_year,
        "period_month": period_month,
        "entity_name": entity_name,
        "status": "open",
        "created_by": str(created_by),
    }
    chain_hash = compute_chain_hash(record_data, previous_hash)

    checklist = MonthEndChecklist(
        tenant_id=tenant_id,
        period_year=period_year,
        period_month=period_month,
        entity_name=entity_name,
        status="open",
        notes=notes,
        created_by=created_by,
        chain_hash=chain_hash,
        previous_hash=previous_hash,
    )
    session.add(checklist)
    await session.flush()

    if add_default_tasks:
        for task_def in DEFAULT_TASKS:
            task = MonthEndTask(
                checklist_id=checklist.id,
                tenant_id=tenant_id,
                task_name=task_def["name"],
                task_category=task_def["category"],
                priority=task_def["priority"],
                sort_order=task_def["sort_order"],
                status="pending",
                is_required=True,
            )
            session.add(task)
        await session.flush()

    return checklist


async def add_task(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    checklist_id: uuid.UUID,
    task_name: str,
    task_category: str = "other",
    priority: str = "medium",
    sort_order: int = 0,
    description: str | None = None,
    assigned_to: uuid.UUID | None = None,
    due_date: date | None = None,
    is_required: bool = True,
) -> MonthEndTask:
    """Add a task to a checklist (UUIDBase — mutable status)."""
    task = MonthEndTask(
        checklist_id=checklist_id,
        tenant_id=tenant_id,
        task_name=task_name,
        task_category=task_category,
        priority=priority,
        sort_order=sort_order,
        description=description,
        assigned_to=assigned_to,
        due_date=due_date,
        is_required=is_required,
        status="pending",
    )
    session.add(task)
    await session.flush()
    return task


async def update_task_status(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    task_id: uuid.UUID,
    status: str,
    completed_by: uuid.UUID | None = None,
    notes: str | None = None,
) -> MonthEndTask | None:
    """Update task status (MonthEndTask is UUIDBase, mutable)."""
    result = await session.execute(
        select(MonthEndTask).where(
            MonthEndTask.id == task_id,
            MonthEndTask.tenant_id == tenant_id,
        )
    )
    task = result.scalar_one_or_none()
    if task is None:
        return None

    task.status = status
    if notes:
        task.notes = notes
    if status == "completed":
        task.completed_at = datetime.now(timezone.utc)
        task.completed_by = completed_by
    await session.flush()
    return task


async def close_checklist(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    checklist_id: uuid.UUID,
    closed_by: uuid.UUID,
    notes: str | None = None,
) -> MonthEndChecklist | None:
    """
    Close a month-end checklist.
    Since MonthEndChecklist is FinancialBase (INSERT ONLY), closing means
    inserting a new record that supersedes the old one.
    """
    result = await session.execute(
        select(MonthEndChecklist).where(
            MonthEndChecklist.id == checklist_id,
            MonthEndChecklist.tenant_id == tenant_id,
        )
    )
    existing = result.scalar_one_or_none()
    if existing is None or existing.status == "closed":
        return existing

    now = datetime.now(timezone.utc)
    previous_hash = await get_previous_hash_locked(session, MonthEndChecklist, tenant_id)
    record_data = {
        "tenant_id": str(tenant_id),
        "period_year": existing.period_year,
        "period_month": existing.period_month,
        "entity_name": existing.entity_name,
        "status": "closed",
        "closed_by": str(closed_by),
    }
    chain_hash = compute_chain_hash(record_data, previous_hash)

    closed = MonthEndChecklist(
        tenant_id=tenant_id,
        period_year=existing.period_year,
        period_month=existing.period_month,
        entity_name=existing.entity_name,
        status="closed",
        closed_at=now,
        closed_by=closed_by,
        notes=notes or existing.notes,
        created_by=existing.created_by,
        chain_hash=chain_hash,
        previous_hash=previous_hash,
    )
    session.add(closed)
    await session.flush()
    return closed


async def get_checklist(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    checklist_id: uuid.UUID,
) -> MonthEndChecklist | None:
    result = await session.execute(
        select(MonthEndChecklist).where(
            MonthEndChecklist.id == checklist_id,
            MonthEndChecklist.tenant_id == tenant_id,
        )
    )
    return result.scalar_one_or_none()


async def list_checklists(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    entity_name: str | None = None,
    status: str | None = None,
    limit: int = 24,
    offset: int = 0,
) -> list[MonthEndChecklist]:
    stmt = select(MonthEndChecklist).where(MonthEndChecklist.tenant_id == tenant_id)
    if entity_name:
        stmt = stmt.where(MonthEndChecklist.entity_name == entity_name)
    if status:
        stmt = stmt.where(MonthEndChecklist.status == status)
    stmt = stmt.order_by(
        desc(MonthEndChecklist.period_year),
        desc(MonthEndChecklist.period_month),
    ).limit(limit).offset(offset)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def list_tasks(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    checklist_id: uuid.UUID,
) -> list[MonthEndTask]:
    result = await session.execute(
        select(MonthEndTask)
        .where(MonthEndTask.checklist_id == checklist_id, MonthEndTask.tenant_id == tenant_id)
        .order_by(MonthEndTask.sort_order, MonthEndTask.created_at)
    )
    return list(result.scalars().all())

