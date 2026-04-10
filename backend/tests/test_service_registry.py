from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.security import create_access_token, hash_password
from financeops.db.models.tenants import IamTenant, TenantStatus, TenantType
from financeops.db.models.users import IamUser, UserRole
from financeops.modules.service_registry.models import ModuleRegistry, TaskRegistry
from financeops.modules.service_registry.service import (
    ensure_registry_seeded,
    get_service_dashboard,
    run_health_checks,
    update_task_stats,
)
from financeops.utils.chain_hash import GENESIS_HASH, compute_chain_hash

PLATFORM_TENANT_ID = uuid.UUID(int=0)

MODULE_SEED = [
    ("mis_manager", "/api/v1/mis", []),
    ("reconciliation", "/api/v1/reconciliation", ["mis_manager"]),
    ("consolidation", "/api/v1/consolidation", ["reconciliation"]),
    ("fixed_assets", "/api/v1/fixed-assets", []),
    ("lease", "/api/v1/leases", []),
    ("revenue", "/api/v1/revenue", []),
    ("payroll_gl", "/api/v1/payroll", []),
    ("board_pack", "/api/v1/board-pack", ["mis_manager"]),
    ("custom_reports", "/api/v1/reports", ["mis_manager"]),
    ("scheduled_delivery", "/api/v1/delivery", ["board_pack", "custom_reports"]),
    ("anomaly_detection", "/api/v1/anomalies", ["mis_manager"]),
    ("erp_sync", "/api/v1/erp", []),
    ("closing_checklist", "/api/v1/close", ["erp_sync", "reconciliation"]),
    ("working_capital", "/api/v1/working-capital", ["mis_manager"]),
    ("expense_management", "/api/v1/expenses", []),
    ("budgeting", "/api/v1/budget", ["mis_manager"]),
    ("forecasting", "/api/v1/forecast", ["budgeting"]),
    ("scenario_modelling", "/api/v1/scenarios", ["forecasting"]),
    ("fdd", "/api/v1/advisory/fdd", ["mis_manager", "working_capital"]),
    ("ppa", "/api/v1/advisory/ppa", ["mis_manager"]),
    ("ma_workspace", "/api/v1/advisory/ma", ["fdd", "ppa"]),
    ("compliance", "/api/v1/compliance", []),
    ("backup", "/api/v1/backup", []),
]

TASK_SEED = [
    ("auto_trigger.trigger_post_sync_pipeline", "erp_sync", "erp_sync", False),
    ("board_pack_generator.generate", "board_pack", "report_gen", False),
    ("scheduled_delivery.poll_due", "scheduled_delivery", "email", True),
    ("auto_trigger.run_anomaly_detection", "anomaly_detection", "ai_inference", False),
    ("metrics.update_queue_depths", "observability", "default", True),
    ("metrics.update_active_tenants", "observability", "default", True),
    ("backup.backup_postgres_daily", "backup", "default", True),
]


def _auth_headers(user: IamUser) -> dict[str, str]:
    token = create_access_token(user.id, user.tenant_id, user.role.value)
    return {"Authorization": f"Bearer {token}"}


async def _ensure_registry_seeded(session: AsyncSession) -> None:
    existing_modules = (
        await session.execute(select(ModuleRegistry.id).limit(1))
    ).scalar_one_or_none()
    if existing_modules is None:
        for module_name, route_prefix, depends_on in MODULE_SEED:
            session.add(
                ModuleRegistry(
                    module_name=module_name,
                    description=f"{module_name} description",
                    route_prefix=route_prefix,
                    depends_on=depends_on,
                )
            )

    existing_tasks = (
        await session.execute(select(TaskRegistry.id).limit(1))
    ).scalar_one_or_none()
    if existing_tasks is None:
        for task_name, module_name, queue_name, is_scheduled in TASK_SEED:
            session.add(
                TaskRegistry(
                    task_name=task_name,
                    module_name=module_name,
                    queue_name=queue_name,
                    description=f"{task_name} description",
                    is_scheduled=is_scheduled,
                )
            )
    await session.flush()


async def _create_platform_user(
    session: AsyncSession,
    *,
    email: str,
    role: UserRole,
) -> IamUser:
    tenant = (
        await session.execute(
            select(IamTenant).where(IamTenant.id == PLATFORM_TENANT_ID)
        )
    ).scalar_one_or_none()
    if tenant is None:
        record_data = {
            "display_name": "FinanceOps Platform",
            "tenant_type": TenantType.direct.value,
            "country": "US",
            "timezone": "UTC",
        }
        session.add(
            IamTenant(
                id=PLATFORM_TENANT_ID,
                tenant_id=PLATFORM_TENANT_ID,
                display_name="FinanceOps Platform",
                tenant_type=TenantType.direct,
                country="US",
                timezone="UTC",
                status=TenantStatus.active,
                is_platform_tenant=True,
                chain_hash=compute_chain_hash(record_data, GENESIS_HASH),
                previous_hash=GENESIS_HASH,
            )
        )
        await session.flush()

    user = IamUser(
        tenant_id=PLATFORM_TENANT_ID,
        email=email,
        hashed_password=hash_password("TestPass123!"),
        full_name="Platform User",
        role=role,
        is_active=True,
        mfa_enabled=True,
    )
    session.add(user)
    await session.flush()
    return user


@pytest.mark.asyncio
async def test_module_registry_seeded(async_session: AsyncSession) -> None:
    await ensure_registry_seeded(async_session)
    rows = (await async_session.execute(select(ModuleRegistry))).scalars().all()
    assert len(rows) >= 20


@pytest.mark.asyncio
async def test_task_registry_seeded(async_session: AsyncSession) -> None:
    await ensure_registry_seeded(async_session)
    rows = (await async_session.execute(select(TaskRegistry))).scalars().all()
    assert len(rows) >= 7


@pytest.mark.asyncio
async def test_module_names_unique(async_session: AsyncSession) -> None:
    await _ensure_registry_seeded(async_session)
    names = (await async_session.execute(select(ModuleRegistry.module_name))).scalars().all()
    assert len(names) == len(set(names))


@pytest.mark.asyncio
async def test_get_service_dashboard_structure(async_session: AsyncSession) -> None:
    payload = await get_service_dashboard(async_session)
    assert "overall_status" in payload
    assert "modules" in payload
    assert "tasks" in payload
    assert "queue_depths" in payload


@pytest.mark.asyncio
async def test_modules_endpoint_auto_seeds_registry(async_client, async_session: AsyncSession) -> None:
    owner = await _create_platform_user(
        async_session,
        email="services.autoseed.owner@example.com",
        role=UserRole.platform_owner,
    )
    response = await async_client.get(
        "/api/v1/platform/services/modules?limit=5&offset=0",
        headers=_auth_headers(owner),
    )
    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["total"] >= 20
    assert payload["data"]


@pytest.mark.asyncio
async def test_overall_status_healthy_when_all_healthy(async_session: AsyncSession) -> None:
    await _ensure_registry_seeded(async_session)
    rows = (await async_session.execute(select(ModuleRegistry))).scalars().all()
    for row in rows:
        row.health_status = "healthy"
    await async_session.flush()

    payload = await get_service_dashboard(async_session)
    assert payload["overall_status"] == "healthy"


@pytest.mark.asyncio
async def test_overall_status_degraded_when_one_unhealthy(async_session: AsyncSession) -> None:
    await _ensure_registry_seeded(async_session)
    rows = (await async_session.execute(select(ModuleRegistry))).scalars().all()
    for row in rows:
        row.health_status = "healthy"
    rows[0].health_status = "unhealthy"
    await async_session.flush()

    payload = await get_service_dashboard(async_session)
    assert payload["overall_status"] == "degraded"


@pytest.mark.asyncio
async def test_unhealthy_modules_list(async_session: AsyncSession) -> None:
    await _ensure_registry_seeded(async_session)
    rows = (await async_session.execute(select(ModuleRegistry))).scalars().all()
    for row in rows:
        row.health_status = "healthy"
    rows[0].health_status = "degraded"
    rows[1].health_status = "unhealthy"
    await async_session.flush()

    payload = await get_service_dashboard(async_session)
    names = {row["module_name"] for row in payload["unhealthy_modules"]}
    assert rows[0].module_name in names
    assert rows[1].module_name in names
    assert all(row["health_status"] != "healthy" for row in payload["unhealthy_modules"])


@pytest.mark.asyncio
async def test_update_task_stats_success(async_session: AsyncSession) -> None:
    await _ensure_registry_seeded(async_session)
    task_name = TASK_SEED[0][0]
    await update_task_stats(async_session, task_name, Decimal("12.34"), success=True)
    row = (
        await async_session.execute(select(TaskRegistry).where(TaskRegistry.task_name == task_name))
    ).scalar_one()
    assert row.last_run_status == "success"


@pytest.mark.asyncio
async def test_update_task_stats_failure(async_session: AsyncSession) -> None:
    await _ensure_registry_seeded(async_session)
    task_name = TASK_SEED[0][0]
    await update_task_stats(async_session, task_name, Decimal("12.34"), success=False)
    row = (
        await async_session.execute(select(TaskRegistry).where(TaskRegistry.task_name == task_name))
    ).scalar_one()
    assert row.last_run_status == "failure"


@pytest.mark.asyncio
async def test_avg_duration_updated(async_session: AsyncSession) -> None:
    await _ensure_registry_seeded(async_session)
    task_name = TASK_SEED[0][0]
    await update_task_stats(async_session, task_name, Decimal("10.00"), success=True)
    await update_task_stats(async_session, task_name, Decimal("20.00"), success=True)
    row = (
        await async_session.execute(select(TaskRegistry).where(TaskRegistry.task_name == task_name))
    ).scalar_one()
    assert Decimal(str(row.avg_duration_seconds)) > Decimal("0")


@pytest.mark.asyncio
async def test_task_stats_duration_is_decimal(async_session: AsyncSession) -> None:
    await _ensure_registry_seeded(async_session)
    task_name = TASK_SEED[0][0]
    await update_task_stats(async_session, task_name, Decimal("8.50"), success=True)
    row = (
        await async_session.execute(select(TaskRegistry).where(TaskRegistry.task_name == task_name))
    ).scalar_one()
    assert isinstance(row.avg_duration_seconds, Decimal)


@pytest.mark.asyncio
async def test_dashboard_endpoint_requires_platform_admin(
    async_client,
    async_session: AsyncSession,
    test_user: IamUser,
) -> None:
    await _ensure_registry_seeded(async_session)
    response = await async_client.get(
        "/api/v1/platform/services/dashboard",
        headers=_auth_headers(test_user),
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_toggle_module_requires_platform_owner(
    async_client,
    async_session: AsyncSession,
) -> None:
    await _ensure_registry_seeded(async_session)
    admin = await _create_platform_user(
        async_session,
        email="services.admin@example.com",
        role=UserRole.platform_admin,
    )
    response = await async_client.patch(
        "/api/v1/platform/services/modules/mis_manager/toggle",
        headers=_auth_headers(admin),
        json={"is_enabled": False},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_modules_list_paginated(async_client, async_session: AsyncSession) -> None:
    await _ensure_registry_seeded(async_session)
    owner = await _create_platform_user(
        async_session,
        email="services.owner@example.com",
        role=UserRole.platform_owner,
    )
    response = await async_client.get(
        "/api/v1/platform/services/modules?limit=5&offset=0",
        headers=_auth_headers(owner),
    )
    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["limit"] == 5
    assert payload["offset"] == 0
    assert payload["total"] >= 20


@pytest.mark.asyncio
async def test_tasks_filtered_by_queue(async_client, async_session: AsyncSession) -> None:
    await _ensure_registry_seeded(async_session)
    owner = await _create_platform_user(
        async_session,
        email="services.queue.owner@example.com",
        role=UserRole.platform_owner,
    )
    response = await async_client.get(
        "/api/v1/platform/services/tasks?queue_name=erp_sync",
        headers=_auth_headers(owner),
    )
    assert response.status_code == 200
    payload = response.json()["data"]["data"]
    assert payload
    assert all(row["queue_name"] == "erp_sync" for row in payload)


@pytest.mark.asyncio
async def test_health_check_updates_last_health_check(async_session: AsyncSession) -> None:
    await _ensure_registry_seeded(async_session)
    await run_health_checks(async_session)
    rows = (await async_session.execute(select(ModuleRegistry))).scalars().all()
    assert all(row.last_health_check is not None for row in rows)


@pytest.mark.asyncio
async def test_toggle_module_changes_flag(async_client, async_session: AsyncSession) -> None:
    await _ensure_registry_seeded(async_session)
    owner = await _create_platform_user(
        async_session,
        email="services.toggle.owner@example.com",
        role=UserRole.platform_owner,
    )
    response = await async_client.patch(
        "/api/v1/platform/services/modules/mis_manager/toggle",
        headers=_auth_headers(owner),
        json={"is_enabled": False},
    )
    assert response.status_code == 200
    assert response.json()["data"]["is_enabled"] is False


@pytest.mark.asyncio
async def test_toggle_module_validation_requires_active_entity_for_enable(
    async_client,
    async_session: AsyncSession,
) -> None:
    await _ensure_registry_seeded(async_session)
    owner = await _create_platform_user(
        async_session,
        email="services.validate.owner@example.com",
        role=UserRole.platform_owner,
    )

    response = await async_client.post(
        "/api/v1/platform/services/modules/mis_manager/toggle/validate",
        headers=_auth_headers(owner),
        json={"is_enabled": True, "entity_id": str(uuid.uuid4())},
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["success"] is False
    assert payload["failure"] is True
    assert "active entity" in payload["reason"].lower()


@pytest.mark.asyncio
async def test_toggle_module_validation_succeeds_for_disable_without_entity(
    async_client,
    async_session: AsyncSession,
) -> None:
    await _ensure_registry_seeded(async_session)
    owner = await _create_platform_user(
        async_session,
        email="services.validate.disable.owner@example.com",
        role=UserRole.platform_owner,
    )

    response = await async_client.post(
        "/api/v1/platform/services/modules/mis_manager/toggle/validate",
        headers=_auth_headers(owner),
        json={"is_enabled": False},
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["success"] is True
    assert payload["failure"] is False
    assert payload["reason"] is None


@pytest.mark.asyncio
async def test_toggle_module_validation_blocks_dependency_cycles(
    async_client,
    async_session: AsyncSession,
) -> None:
    await _ensure_registry_seeded(async_session)
    owner = await _create_platform_user(
        async_session,
        email="services.validate.cycle.owner@example.com",
        role=UserRole.platform_owner,
    )

    mis_manager = (
        await async_session.execute(
            select(ModuleRegistry).where(ModuleRegistry.module_name == "mis_manager")
        )
    ).scalar_one()
    reconciliation = (
        await async_session.execute(
            select(ModuleRegistry).where(ModuleRegistry.module_name == "reconciliation")
        )
    ).scalar_one()
    mis_manager.depends_on = ["reconciliation"]
    reconciliation.depends_on = ["mis_manager"]
    await async_session.flush()

    response = await async_client.post(
        "/api/v1/platform/services/modules/mis_manager/toggle/validate",
        headers=_auth_headers(owner),
        json={"is_enabled": True},
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["success"] is False
    assert payload["failure"] is True
    assert "cycle" in payload["reason"].lower()


@pytest.mark.asyncio
async def test_tasks_filter_by_scheduled(async_client, async_session: AsyncSession) -> None:
    await _ensure_registry_seeded(async_session)
    owner = await _create_platform_user(
        async_session,
        email="services.scheduled.owner@example.com",
        role=UserRole.platform_owner,
    )
    response = await async_client.get(
        "/api/v1/platform/services/tasks?is_scheduled=true",
        headers=_auth_headers(owner),
    )
    assert response.status_code == 200
    rows = response.json()["data"]["data"]
    assert rows
    assert all(row["is_scheduled"] is True for row in rows)


@pytest.mark.asyncio
async def test_dashboard_includes_queue_depth_defaults(async_session: AsyncSession) -> None:
    await _ensure_registry_seeded(async_session)
    payload = await get_service_dashboard(async_session)
    for queue_name in (
        "file_scan",
        "parse",
        "erp_sync",
        "report_gen",
        "email",
        "ai_inference",
        "notification",
        "default",
    ):
        assert queue_name in payload["queue_depths"]


@pytest.mark.asyncio
async def test_health_check_endpoint_runs(async_client, async_session: AsyncSession) -> None:
    await _ensure_registry_seeded(async_session)
    admin = await _create_platform_user(
        async_session,
        email="services.health.admin@example.com",
        role=UserRole.platform_admin,
    )
    response = await async_client.post(
        "/api/v1/platform/services/health-check",
        headers=_auth_headers(admin),
    )
    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["total"] >= 20
    assert "modules" in payload


@pytest.mark.asyncio
async def test_update_task_stats_sets_last_run_at(async_session: AsyncSession) -> None:
    await _ensure_registry_seeded(async_session)
    task_name = TASK_SEED[0][0]
    before = datetime.now(UTC)
    await update_task_stats(async_session, task_name, Decimal("1.50"), success=True)
    row = (
        await async_session.execute(select(TaskRegistry).where(TaskRegistry.task_name == task_name))
    ).scalar_one()
    assert row.last_run_at is not None
    assert row.last_run_at >= before
