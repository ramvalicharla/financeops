from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.modules.closing_checklist.models import ChecklistRun, ChecklistRunTask
from financeops.modules.search.service import upsert_index_entry


async def index_checklist_task(session: AsyncSession, task: ChecklistRunTask) -> None:
    run = (
        await session.execute(select(ChecklistRun).where(ChecklistRun.id == task.run_id))
    ).scalar_one_or_none()
    period = run.period if run is not None else "unknown"
    await upsert_index_entry(
        session,
        tenant_id=task.tenant_id,
        entity_type="checklist_task",
        entity_id=task.id,
        title=task.task_name,
        subtitle=f"Close {period}",
        body=task.notes,
        url=f"/close/{period}",
        metadata={
            "status": task.status,
            "assigned_to": str(task.assigned_to) if task.assigned_to else None,
        },
    )


async def reindex_all_checklist_tasks(session: AsyncSession, tenant_id: uuid.UUID) -> int:
    rows = (
        await session.execute(
            select(ChecklistRunTask).where(ChecklistRunTask.tenant_id == tenant_id)
        )
    ).scalars().all()
    for row in rows:
        await index_checklist_task(session, row)
    return len(rows)


__all__ = ["index_checklist_task", "reindex_all_checklist_tasks"]

