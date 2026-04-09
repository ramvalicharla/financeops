from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.intent.context import MutationContext, governed_mutation_context
from financeops.core.security import create_access_token, hash_password
from financeops.db.models.tenants import IamTenant, TenantStatus, TenantType
from financeops.db.models.users import IamUser, UserRole
from financeops.modules.closing_checklist.models import (
    ChecklistRun,
    ChecklistRunTask,
    ChecklistTemplate,
    ChecklistTemplateTask,
)
from financeops.modules.closing_checklist.service import (
    DependencyNotMetError,
    auto_complete_task as _auto_complete_task,
    compute_progress,
    get_or_create_run as _get_or_create_run,
    period_end_date,
    update_task_status as _update_task_status,
)
from financeops.utils.chain_hash import GENESIS_HASH, compute_chain_hash


def _governed_context(intent_type: str) -> MutationContext:
    return MutationContext(
        intent_id=uuid.uuid4(),
        job_id=uuid.uuid4(),
        actor_user_id=None,
        actor_role=UserRole.finance_leader.value,
        intent_type=intent_type,
    )


async def get_or_create_run(*args, **kwargs):
    with governed_mutation_context(_governed_context("ENSURE_CHECKLIST_RUN")):
        return await _get_or_create_run(*args, **kwargs)


async def update_task_status(*args, **kwargs):
    with governed_mutation_context(_governed_context("UPDATE_CHECKLIST_TASK_STATUS")):
        return await _update_task_status(*args, **kwargs)


async def auto_complete_task(*args, **kwargs):
    with governed_mutation_context(_governed_context("AUTO_COMPLETE_CHECKLIST_TASKS")):
        return await _auto_complete_task(*args, **kwargs)


async def _seed_default_template(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    created_by: uuid.UUID,
) -> ChecklistTemplate:
    existing = (
        await session.execute(
            select(ChecklistTemplate).where(
                ChecklistTemplate.tenant_id == tenant_id,
                ChecklistTemplate.is_default.is_(True),
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    template = ChecklistTemplate(
        tenant_id=tenant_id,
        name="Default Month-End Close Checklist",
        description="seeded",
        is_default=True,
        created_by=created_by,
    )
    session.add(template)
    await session.flush()

    task_defs = [
        ("ERP data sync complete", -3, None, "erp_sync_complete", []),
        ("GL/TB reconciliation", -2, None, "recon_complete", [1]),
        ("Intercompany reconciliation", -2, None, None, [2]),
        ("Payroll upload and reconciliation", -1, "data_entry_payroll", None, []),
        ("Prepaid and accrual adjustments", 0, "manager", None, [2]),
        ("Fixed asset depreciation run", 0, None, None, [2]),
        ("Multi-entity consolidation", 1, None, "consolidation_complete", [3, 5, 6]),
        ("FX rate confirmation", 0, None, None, []),
        ("MIS review and approval", 2, "finance_leader", None, [7]),
        ("Anomaly detection review", 2, None, "anomaly_detection_complete", [7]),
        ("Board pack generation", 3, None, "board_pack_generated", [9, 10]),
        ("Finance Leader sign-off", 4, "finance_leader", None, [11]),
    ]

    ids = [uuid.uuid4() for _ in task_defs]
    for index, (name, days_relative, role, event, depends) in enumerate(task_defs, start=1):
        session.add(
            ChecklistTemplateTask(
                id=ids[index - 1],
                template_id=template.id,
                tenant_id=tenant_id,
                task_name=name,
                assigned_role=role,
                days_relative_to_period_end=days_relative,
                depends_on_task_ids=[str(ids[item - 1]) for item in depends],
                auto_trigger_event=event,
                order_index=index,
            )
        )

    await session.flush()
    return template


async def _get_tasks(session: AsyncSession, run_id: uuid.UUID) -> list[ChecklistRunTask]:
    return (
        await session.execute(
            select(ChecklistRunTask)
            .where(ChecklistRunTask.run_id == run_id)
            .order_by(ChecklistRunTask.order_index.asc())
        )
    ).scalars().all()


@pytest.mark.asyncio
async def test_default_template_seeded_for_tenant(async_session: AsyncSession, test_user: IamUser) -> None:
    """Assert default template with 12 tasks exists after migration."""
    template = await _seed_default_template(async_session, tenant_id=test_user.tenant_id, created_by=test_user.id)
    tasks = (
        await async_session.execute(
            select(ChecklistTemplateTask).where(ChecklistTemplateTask.template_id == template.id)
        )
    ).scalars().all()
    assert template.is_default is True
    assert len(tasks) == 12


@pytest.mark.asyncio
async def test_get_or_create_run_creates_new(async_session: AsyncSession, test_user: IamUser) -> None:
    """Call get_or_create_run for a new period and ensure 12 not_started tasks."""
    await _seed_default_template(async_session, tenant_id=test_user.tenant_id, created_by=test_user.id)
    run = await get_or_create_run(async_session, test_user.tenant_id, "2025-03", test_user.id)
    tasks = await _get_tasks(async_session, run.id)
    assert len(tasks) == 12
    assert all(task.status == "not_started" for task in tasks)


@pytest.mark.asyncio
async def test_get_or_create_run_idempotent(async_session: AsyncSession, test_user: IamUser) -> None:
    """Calling get_or_create_run twice returns the same run."""
    await _seed_default_template(async_session, tenant_id=test_user.tenant_id, created_by=test_user.id)
    first = await get_or_create_run(async_session, test_user.tenant_id, "2025-03", test_user.id)
    second = await get_or_create_run(async_session, test_user.tenant_id, "2025-03", test_user.id)
    count = (
        await async_session.execute(
            select(func.count()).select_from(ChecklistRun).where(
                ChecklistRun.tenant_id == test_user.tenant_id,
                ChecklistRun.period == "2025-03",
            )
        )
    ).scalar_one()
    assert first.id == second.id
    assert count == 1


from sqlalchemy import func


@pytest.mark.asyncio
async def test_run_unique_constraint_per_tenant_per_period(async_session: AsyncSession, test_user: IamUser) -> None:
    """Two tenants same period create independent runs without leakage."""
    await _seed_default_template(async_session, tenant_id=test_user.tenant_id, created_by=test_user.id)
    run_a = await get_or_create_run(async_session, test_user.tenant_id, "2025-03", test_user.id)

    tenant_b = uuid.uuid4()
    tenant_b_chain = compute_chain_hash(
        {
            "display_name": "Tenant B",
            "tenant_type": TenantType.direct.value,
            "country": "US",
            "timezone": "UTC",
        },
        GENESIS_HASH,
    )
    async_session.add(
        IamTenant(
            id=tenant_b,
            tenant_id=tenant_b,
            display_name="Tenant B",
            tenant_type=TenantType.direct,
            country="US",
            timezone="UTC",
            status=TenantStatus.active,
            chain_hash=tenant_b_chain,
            previous_hash=GENESIS_HASH,
        )
    )
    await async_session.flush()

    user_b = IamUser(
        tenant_id=tenant_b,
        email=f"tenantb-{uuid.uuid4().hex[:6]}@example.com",
        hashed_password=hash_password("TestPass123!"),
        full_name="Tenant B",
        role=UserRole.finance_leader,
        is_active=True,
        mfa_enabled=False,
    )
    async_session.add(user_b)
    await async_session.flush()
    await _seed_default_template(async_session, tenant_id=tenant_b, created_by=user_b.id)

    run_b = await get_or_create_run(async_session, tenant_b, "2025-03", user_b.id)

    assert run_a.tenant_id != run_b.tenant_id
    assert run_a.id != run_b.id


@pytest.mark.asyncio
async def test_task_due_dates_computed_from_period(async_session: AsyncSession, test_user: IamUser) -> None:
    """Task due_date uses period-end convention for days_relative offsets."""
    await _seed_default_template(async_session, tenant_id=test_user.tenant_id, created_by=test_user.id)
    run = await get_or_create_run(async_session, test_user.tenant_id, "2025-03", test_user.id)
    tasks = await _get_tasks(async_session, run.id)
    task1 = tasks[0]
    assert task1.due_date == date(2025, 3, 28)


@pytest.mark.asyncio
async def test_progress_starts_at_zero(async_session: AsyncSession, test_user: IamUser) -> None:
    """New run has progress_pct == Decimal('0.00')."""
    await _seed_default_template(async_session, tenant_id=test_user.tenant_id, created_by=test_user.id)
    run = await get_or_create_run(async_session, test_user.tenant_id, "2025-03", test_user.id)
    assert run.progress_pct == Decimal("0.00")


@pytest.mark.asyncio
async def test_update_task_to_in_progress(async_session: AsyncSession, test_user: IamUser) -> None:
    """Setting one task to in_progress updates run status to in_progress."""
    await _seed_default_template(async_session, tenant_id=test_user.tenant_id, created_by=test_user.id)
    run = await get_or_create_run(async_session, test_user.tenant_id, "2025-03", test_user.id)
    task = (await _get_tasks(async_session, run.id))[0]

    await update_task_status(async_session, test_user.tenant_id, run.id, task.id, "in_progress", test_user.id)
    refreshed = await async_session.get(ChecklistRun, run.id)
    assert refreshed is not None
    assert refreshed.status == "in_progress"


@pytest.mark.asyncio
async def test_complete_task_without_dependency(async_session: AsyncSession, test_user: IamUser) -> None:
    """Task without dependencies can be completed directly."""
    await _seed_default_template(async_session, tenant_id=test_user.tenant_id, created_by=test_user.id)
    run = await get_or_create_run(async_session, test_user.tenant_id, "2025-03", test_user.id)
    task = (await _get_tasks(async_session, run.id))[0]

    updated = await update_task_status(async_session, test_user.tenant_id, run.id, task.id, "completed", test_user.id)
    refreshed = await async_session.get(ChecklistRun, run.id)

    assert updated.completed_at is not None
    assert refreshed is not None
    assert refreshed.progress_pct > Decimal("0")


@pytest.mark.asyncio
async def test_dependency_blocks_completion(async_session: AsyncSession, test_user: IamUser) -> None:
    """Task with unmet dependency cannot be completed."""
    await _seed_default_template(async_session, tenant_id=test_user.tenant_id, created_by=test_user.id)
    run = await get_or_create_run(async_session, test_user.tenant_id, "2025-03", test_user.id)
    tasks = await _get_tasks(async_session, run.id)
    task_b = tasks[1]

    with pytest.raises(DependencyNotMetError):
        await update_task_status(async_session, test_user.tenant_id, run.id, task_b.id, "completed", test_user.id)

    refreshed = await async_session.get(ChecklistRunTask, task_b.id)
    assert refreshed is not None
    assert refreshed.status == "not_started"


@pytest.mark.asyncio
async def test_dependency_unblocks_after_prerequisite(async_session: AsyncSession, test_user: IamUser) -> None:
    """Task B can complete after dependent Task A is completed first."""
    await _seed_default_template(async_session, tenant_id=test_user.tenant_id, created_by=test_user.id)
    run = await get_or_create_run(async_session, test_user.tenant_id, "2025-03", test_user.id)
    tasks = await _get_tasks(async_session, run.id)
    task_a = tasks[0]
    task_b = tasks[1]

    await update_task_status(async_session, test_user.tenant_id, run.id, task_a.id, "completed", test_user.id)
    updated_b = await update_task_status(async_session, test_user.tenant_id, run.id, task_b.id, "completed", test_user.id)

    assert updated_b.status == "completed"


@pytest.mark.asyncio
async def test_all_tasks_complete_sets_run_completed(async_session: AsyncSession, test_user: IamUser) -> None:
    """Completing all tasks sets run.status=completed and progress=100."""
    await _seed_default_template(async_session, tenant_id=test_user.tenant_id, created_by=test_user.id)
    run = await get_or_create_run(async_session, test_user.tenant_id, "2025-03", test_user.id)

    ordered = await _get_tasks(async_session, run.id)
    for task in ordered:
        try:
            await update_task_status(async_session, test_user.tenant_id, run.id, task.id, "completed", test_user.id)
        except DependencyNotMetError:
            continue
    # second pass clears forward dependencies
    ordered = await _get_tasks(async_session, run.id)
    for task in ordered:
        if task.status != "completed":
            await update_task_status(async_session, test_user.tenant_id, run.id, task.id, "completed", test_user.id)

    refreshed = await async_session.get(ChecklistRun, run.id)
    assert refreshed is not None
    assert refreshed.status == "completed"
    assert refreshed.actual_close_date == date.today()
    assert refreshed.progress_pct == Decimal("100.00")


@pytest.mark.asyncio
async def test_progress_recomputed_after_each_task(async_session: AsyncSession, test_user: IamUser) -> None:
    """Three completed tasks out of 12 yields 25% progress."""
    await _seed_default_template(async_session, tenant_id=test_user.tenant_id, created_by=test_user.id)
    run = await get_or_create_run(async_session, test_user.tenant_id, "2025-03", test_user.id)

    tasks = await _get_tasks(async_session, run.id)
    await update_task_status(async_session, test_user.tenant_id, run.id, tasks[0].id, "completed", test_user.id)
    await update_task_status(async_session, test_user.tenant_id, run.id, tasks[1].id, "completed", test_user.id)
    await update_task_status(async_session, test_user.tenant_id, run.id, tasks[2].id, "completed", test_user.id)

    refreshed = await async_session.get(ChecklistRun, run.id)
    assert refreshed is not None
    assert refreshed.progress_pct == Decimal("25.00")


@pytest.mark.asyncio
async def test_skipped_task_counts_as_complete_for_progress(async_session: AsyncSession, test_user: IamUser) -> None:
    """Skipped task contributes to progress as complete."""
    await _seed_default_template(async_session, tenant_id=test_user.tenant_id, created_by=test_user.id)
    run = await get_or_create_run(async_session, test_user.tenant_id, "2025-03", test_user.id)
    tasks = await _get_tasks(async_session, run.id)

    await update_task_status(async_session, test_user.tenant_id, run.id, tasks[0].id, "skipped", test_user.id)
    for task in tasks[1:]:
        try:
            await update_task_status(async_session, test_user.tenant_id, run.id, task.id, "completed", test_user.id)
        except DependencyNotMetError:
            continue
    for task in await _get_tasks(async_session, run.id):
        if task.status not in {"completed", "skipped"}:
            await update_task_status(async_session, test_user.tenant_id, run.id, task.id, "completed", test_user.id)

    refreshed = await async_session.get(ChecklistRun, run.id)
    assert refreshed is not None
    assert refreshed.progress_pct == Decimal("100.00")


@pytest.mark.asyncio
async def test_role_restriction_enforced(async_client: AsyncClient, async_session: AsyncSession, test_user: IamUser, test_access_token: str) -> None:
    """Assigned-role mismatch returns 403 while Finance Leader override works."""
    await _seed_default_template(async_session, tenant_id=test_user.tenant_id, created_by=test_user.id)
    run = await get_or_create_run(async_session, test_user.tenant_id, "2025-03", test_user.id)
    task = (await _get_tasks(async_session, run.id))[3]

    reviewer = IamUser(
        tenant_id=test_user.tenant_id,
        email=f"reviewer-{uuid.uuid4().hex[:6]}@example.com",
        hashed_password=hash_password("TestPass123!"),
        full_name="Reviewer",
        role=UserRole.read_only,
        is_active=True,
        mfa_enabled=False,
    )
    async_session.add(reviewer)
    await async_session.flush()
    reviewer_token = create_access_token(reviewer.id, reviewer.tenant_id, reviewer.role.value)

    denied = await async_client.patch(
        f"/api/v1/close/2025-03/tasks/{task.id}",
        headers={"Authorization": f"Bearer {reviewer_token}"},
        json={"status": "in_progress"},
    )
    assert denied.status_code == 403

    allowed = await async_client.patch(
        f"/api/v1/close/2025-03/tasks/{task.id}",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={"status": "in_progress"},
    )
    assert allowed.status_code == 200


@pytest.mark.asyncio
async def test_auto_complete_on_erp_sync_event(async_session: AsyncSession, test_user: IamUser) -> None:
    """ERP sync event auto-completes task 1."""
    await _seed_default_template(async_session, tenant_id=test_user.tenant_id, created_by=test_user.id)
    run = await get_or_create_run(async_session, test_user.tenant_id, "2025-03", test_user.id)

    updated = await auto_complete_task(async_session, test_user.tenant_id, "2025-03", "erp_sync_complete")
    task1 = (await _get_tasks(async_session, run.id))[0]

    assert updated
    assert task1.status == "completed"
    assert task1.is_auto_completed is True
    assert task1.auto_completed_by_event == "erp_sync_complete"


@pytest.mark.asyncio
async def test_auto_complete_on_recon_event(async_session: AsyncSession, test_user: IamUser) -> None:
    """Recon event auto-completes GL/TB task when dependencies are met."""
    await _seed_default_template(async_session, tenant_id=test_user.tenant_id, created_by=test_user.id)
    run = await get_or_create_run(async_session, test_user.tenant_id, "2025-03", test_user.id)
    tasks = await _get_tasks(async_session, run.id)
    await update_task_status(async_session, test_user.tenant_id, run.id, tasks[0].id, "completed", test_user.id)

    await auto_complete_task(async_session, test_user.tenant_id, "2025-03", "recon_complete")
    refreshed = await _get_tasks(async_session, run.id)
    assert refreshed[1].status == "completed"


@pytest.mark.asyncio
async def test_auto_complete_does_not_fire_without_run(async_session: AsyncSession, test_user: IamUser) -> None:
    """Auto-complete on missing period is a no-op and creates no run."""
    await _seed_default_template(async_session, tenant_id=test_user.tenant_id, created_by=test_user.id)
    updated = await auto_complete_task(async_session, test_user.tenant_id, "2025-04", "erp_sync_complete")
    count = (
        await async_session.execute(
            select(func.count()).select_from(ChecklistRun).where(
                ChecklistRun.tenant_id == test_user.tenant_id,
                ChecklistRun.period == "2025-04",
            )
        )
    ).scalar_one()
    assert updated == []
    assert count == 0


@pytest.mark.asyncio
async def test_auto_complete_progress_recomputed(async_session: AsyncSession, test_user: IamUser) -> None:
    """Auto-completing two tasks updates run progress percentage."""
    await _seed_default_template(async_session, tenant_id=test_user.tenant_id, created_by=test_user.id)
    run = await get_or_create_run(async_session, test_user.tenant_id, "2025-03", test_user.id)
    tasks = await _get_tasks(async_session, run.id)
    await update_task_status(async_session, test_user.tenant_id, run.id, tasks[0].id, "completed", test_user.id)
    await auto_complete_task(async_session, test_user.tenant_id, "2025-03", "recon_complete")

    refreshed = await async_session.get(ChecklistRun, run.id)
    assert refreshed is not None
    assert refreshed.progress_pct == Decimal("16.67")


@pytest.mark.asyncio
async def test_auto_complete_only_for_current_period(async_session: AsyncSession, test_user: IamUser) -> None:
    """Event auto-complete applies only to the target period run."""
    await _seed_default_template(async_session, tenant_id=test_user.tenant_id, created_by=test_user.id)
    run_feb = await get_or_create_run(async_session, test_user.tenant_id, "2025-02", test_user.id)
    run_mar = await get_or_create_run(async_session, test_user.tenant_id, "2025-03", test_user.id)

    await auto_complete_task(async_session, test_user.tenant_id, "2025-03", "erp_sync_complete")
    feb_task = (await _get_tasks(async_session, run_feb.id))[0]
    mar_task = (await _get_tasks(async_session, run_mar.id))[0]

    assert feb_task.status == "not_started"
    assert mar_task.status == "completed"


@pytest.mark.asyncio
async def test_get_checklist_creates_run_if_missing(async_client: AsyncClient, test_access_token: str) -> None:
    """GET /api/v1/close/{period} creates run and returns tasks."""
    response = await async_client.get(
        "/api/v1/close/2025-03",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 200
    payload = response.json()["data"]
    assert "run" in payload
    assert "tasks" in payload


@pytest.mark.asyncio
async def test_get_checklist_returns_dependency_met_flag(async_client: AsyncClient, test_access_token: str) -> None:
    """Checklist payload contains dependency_met boolean for each task."""
    response = await async_client.get(
        "/api/v1/close/2025-03",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 200
    tasks = response.json()["data"]["tasks"]
    assert tasks
    assert all("dependency_met" in task for task in tasks)


@pytest.mark.asyncio
async def test_patch_task_status(async_client: AsyncClient, test_access_token: str) -> None:
    """PATCH updates task status and returns updated payload."""
    initial = await async_client.get(
        "/api/v1/close/2025-03",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    task_id = initial.json()["data"]["tasks"][0]["id"]
    response = await async_client.patch(
        f"/api/v1/close/2025-03/tasks/{task_id}",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={"status": "in_progress"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["task"]["status"] == "in_progress"


@pytest.mark.asyncio
async def test_patch_task_blocked_by_dependency_returns_422(async_client: AsyncClient, test_access_token: str) -> None:
    """PATCH to completed with unmet dependency returns 422 naming blocker."""
    initial = await async_client.get(
        "/api/v1/close/2025-03",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    task_id = initial.json()["data"]["tasks"][1]["id"]
    response = await async_client.patch(
        f"/api/v1/close/2025-03/tasks/{task_id}",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={"status": "completed"},
    )
    assert response.status_code == 422
    assert "Complete" in response.json()["error"]["message"]


@pytest.mark.asyncio
async def test_history_paginated(async_client: AsyncClient, test_access_token: str) -> None:
    """History endpoint returns paginated data envelope."""
    response = await async_client.get(
        "/api/v1/close/history?limit=5&offset=0",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 200
    payload = response.json()["data"]
    assert {"data", "total", "limit", "offset"}.issubset(payload.keys())


@pytest.mark.asyncio
async def test_analytics_returns_correct_structure(async_client: AsyncClient, test_access_token: str) -> None:
    """Analytics endpoint returns required fields with decimal strings."""
    response = await async_client.get(
        "/api/v1/close/analytics",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 200
    payload = response.json()["data"]
    assert "avg_days_to_close" in payload
    assert "on_time_rate" in payload
    assert "trend" in payload
    assert isinstance(payload["avg_days_to_close"], str)
    assert isinstance(payload["on_time_rate"], str)
