from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.services.monthend_service import (
    add_task,
    close_checklist,
    create_checklist,
    get_checklist,
    list_checklists,
    list_tasks,
    update_task_status,
)


@pytest.mark.asyncio
async def test_create_checklist_with_default_tasks(
    async_session: AsyncSession, test_tenant
):
    """Creating a checklist with add_default_tasks=True generates 10 tasks."""
    checklist = await create_checklist(
        async_session,
        tenant_id=test_tenant.id,
        period_year=2025,
        period_month=3,
        entity_name="ME_Entity",
        created_by=test_tenant.id,
        add_default_tasks=True,
    )
    assert checklist.status == "open"
    assert len(checklist.chain_hash) == 64

    tasks = await list_tasks(async_session, test_tenant.id, checklist.id)
    assert len(tasks) == 10
    assert tasks[0].task_name == "Upload Trial Balance"
    assert tasks[0].status == "pending"


@pytest.mark.asyncio
async def test_create_checklist_without_default_tasks(
    async_session: AsyncSession, test_tenant
):
    """No default tasks when add_default_tasks=False."""
    checklist = await create_checklist(
        async_session,
        tenant_id=test_tenant.id,
        period_year=2025,
        period_month=4,
        entity_name="ME_Entity_NoTasks",
        created_by=test_tenant.id,
        add_default_tasks=False,
    )
    tasks = await list_tasks(async_session, test_tenant.id, checklist.id)
    assert tasks == []


@pytest.mark.asyncio
async def test_add_custom_task(async_session: AsyncSession, test_tenant):
    checklist = await create_checklist(
        async_session,
        tenant_id=test_tenant.id,
        period_year=2025,
        period_month=5,
        entity_name="ME_Custom",
        created_by=test_tenant.id,
        add_default_tasks=False,
    )
    task = await add_task(
        async_session,
        tenant_id=test_tenant.id,
        checklist_id=checklist.id,
        task_name="Custom Audit Review",
        task_category="approval",
        priority="high",
        sort_order=1,
    )
    assert task.task_name == "Custom Audit Review"
    assert task.status == "pending"
    assert task.priority == "high"


@pytest.mark.asyncio
async def test_update_task_status_to_completed(
    async_session: AsyncSession, test_tenant
):
    checklist = await create_checklist(
        async_session,
        tenant_id=test_tenant.id,
        period_year=2025,
        period_month=6,
        entity_name="ME_Update",
        created_by=test_tenant.id,
        add_default_tasks=True,
    )
    tasks = await list_tasks(async_session, test_tenant.id, checklist.id)
    task_id = tasks[0].id

    updated = await update_task_status(
        async_session,
        tenant_id=test_tenant.id,
        task_id=task_id,
        status="completed",
        completed_by=test_tenant.id,
    )
    assert updated is not None
    assert updated.status == "completed"
    assert updated.completed_at is not None
    assert updated.completed_by == test_tenant.id


@pytest.mark.asyncio
async def test_close_checklist_creates_new_record(
    async_session: AsyncSession, test_tenant
):
    """Closing a checklist uses INSERT ONLY — creates a new closed record."""
    checklist = await create_checklist(
        async_session,
        tenant_id=test_tenant.id,
        period_year=2025,
        period_month=7,
        entity_name="ME_Close",
        created_by=test_tenant.id,
        add_default_tasks=False,
    )
    original_id = checklist.id

    closed = await close_checklist(
        async_session,
        tenant_id=test_tenant.id,
        checklist_id=checklist.id,
        closed_by=test_tenant.id,
        notes="Period closed",
    )
    assert closed is not None
    assert closed.status == "closed"
    assert closed.closed_at is not None
    # A new row is inserted, so the new closed record has a different id
    assert closed.id != original_id
    assert closed.period_year == 2025
    assert closed.period_month == 7
    assert len(closed.chain_hash) == 64


@pytest.mark.asyncio
async def test_get_checklist_returns_correct_record(
    async_session: AsyncSession, test_tenant
):
    checklist = await create_checklist(
        async_session,
        tenant_id=test_tenant.id,
        period_year=2025,
        period_month=8,
        entity_name="ME_Get",
        created_by=test_tenant.id,
        add_default_tasks=False,
    )
    fetched = await get_checklist(async_session, test_tenant.id, checklist.id)
    assert fetched is not None
    assert fetched.id == checklist.id
    assert fetched.entity_name == "ME_Get"
