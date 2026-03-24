from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

import httpx
from httpx import ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.modules.service_registry.models import ModuleRegistry, TaskRegistry
from financeops.observability.celery_monitor import get_celery_monitor

_ALLOWED_ROUTE_STATUSES = {200, 204, 401, 403, 405, 422}
_QUEUE_NAMES = (
    "file_scan",
    "parse",
    "erp_sync",
    "report_gen",
    "email",
    "ai_inference",
    "notification",
    "default",
)


def _q2(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _q4(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


async def _check_route_prefix(route_prefix: str | None) -> bool:
    if not route_prefix:
        return True
    try:
        from financeops.main import app

        try:
            transport = ASGITransport(app=app, raise_app_exceptions=False, lifespan="off")
        except TypeError:
            transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://financeops.internal",
            timeout=5.0,
        ) as client:
            head_response = await client.head(route_prefix)
            if head_response.status_code in _ALLOWED_ROUTE_STATUSES:
                return True
            options_response = await client.options(route_prefix)
            return options_response.status_code in _ALLOWED_ROUTE_STATUSES
    except Exception:
        return False


def _depends_on_healthy(module: ModuleRegistry, status_by_module: dict[str, str]) -> bool:
    dependencies = list(module.depends_on or [])
    if not dependencies:
        return True
    for dependency in dependencies:
        if status_by_module.get(str(dependency)) != "healthy":
            return False
    return True


async def run_health_checks(session: AsyncSession) -> dict[str, Any]:
    rows = (
        await session.execute(select(ModuleRegistry).order_by(ModuleRegistry.module_name.asc()))
    ).scalars().all()

    now = datetime.now(UTC)
    route_ok_by_module: dict[str, bool] = {}
    status_by_module: dict[str, str] = {
        row.module_name: str(row.health_status or "unknown")
        for row in rows
    }

    for row in rows:
        route_ok_by_module[row.module_name] = await _check_route_prefix(row.route_prefix)

    for row in rows:
        if not row.is_enabled:
            next_status = "unknown"
        else:
            route_ok = route_ok_by_module.get(row.module_name, False)
            deps_healthy = _depends_on_healthy(row, status_by_module)
            if route_ok and deps_healthy:
                next_status = "healthy"
            elif route_ok and not deps_healthy:
                next_status = "degraded"
            else:
                next_status = "unhealthy"

        row.health_status = next_status
        row.last_health_check = now
        row.updated_at = now
        status_by_module[row.module_name] = next_status

    summary = {"total": len(rows), "healthy": 0, "degraded": 0, "unhealthy": 0, "unknown": 0}
    modules: list[dict[str, Any]] = []
    for row in rows:
        status_value = str(row.health_status or "unknown")
        summary[status_value] = summary.get(status_value, 0) + 1
        modules.append(
            {
                "module_name": row.module_name,
                "module_version": row.module_version,
                "description": row.description,
                "is_enabled": row.is_enabled,
                "health_status": status_value,
                "last_health_check": row.last_health_check,
                "route_prefix": row.route_prefix,
                "depends_on": list(row.depends_on or []),
            }
        )

    await session.flush()
    return {**summary, "modules": modules}


async def update_task_stats(
    session: AsyncSession,
    task_name: str,
    duration_seconds: Decimal,
    success: bool,
) -> None:
    row = (
        await session.execute(
            select(TaskRegistry).where(TaskRegistry.task_name == task_name)
        )
    ).scalar_one_or_none()
    if row is None:
        return

    now = datetime.now(UTC)
    duration = _q2(Decimal(str(duration_seconds)))
    if row.avg_duration_seconds is None:
        row.avg_duration_seconds = duration
    else:
        old_duration = Decimal(str(row.avg_duration_seconds))
        row.avg_duration_seconds = _q2((old_duration + duration) / Decimal("2"))

    previous_success_rate = (
        Decimal(str(row.success_rate_7d))
        if row.success_rate_7d is not None
        else None
    )
    run_score = Decimal("1") if success else Decimal("0")
    if previous_success_rate is None:
        row.success_rate_7d = _q4(run_score)
    else:
        row.success_rate_7d = _q4((previous_success_rate * Decimal("0.9")) + (run_score * Decimal("0.1")))

    row.last_run_at = now
    row.last_run_status = "success" if success else "failure"
    row.updated_at = now
    await session.flush()


def _serialize_module(row: ModuleRegistry) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "module_name": row.module_name,
        "module_version": row.module_version,
        "description": row.description,
        "is_enabled": row.is_enabled,
        "health_status": row.health_status,
        "last_health_check": row.last_health_check.isoformat() if row.last_health_check else None,
        "route_prefix": row.route_prefix,
        "depends_on": list(row.depends_on or []),
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


def _serialize_task(row: TaskRegistry) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "task_name": row.task_name,
        "module_name": row.module_name,
        "queue_name": row.queue_name,
        "description": row.description,
        "avg_duration_seconds": format(Decimal(str(row.avg_duration_seconds)), "f")
        if row.avg_duration_seconds is not None
        else None,
        "success_rate_7d": format(Decimal(str(row.success_rate_7d)), "f")
        if row.success_rate_7d is not None
        else None,
        "last_run_at": row.last_run_at.isoformat() if row.last_run_at else None,
        "last_run_status": row.last_run_status,
        "is_scheduled": row.is_scheduled,
        "schedule_cron": row.schedule_cron,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


async def get_service_dashboard(session: AsyncSession) -> dict[str, Any]:
    modules = (
        await session.execute(select(ModuleRegistry).order_by(ModuleRegistry.module_name.asc()))
    ).scalars().all()
    tasks = (
        await session.execute(select(TaskRegistry).order_by(TaskRegistry.task_name.asc()))
    ).scalars().all()

    monitor = get_celery_monitor()
    try:
        queue_depths = await monitor.get_queue_depths()
    except Exception:
        queue_depths = {}
    for queue_name in _QUEUE_NAMES:
        queue_depths.setdefault(queue_name, 0)

    module_statuses = [str(row.health_status or "unknown") for row in modules]
    if module_statuses and all(status == "healthy" for status in module_statuses):
        overall_status = "healthy"
    elif module_statuses and all(status == "unhealthy" for status in module_statuses):
        overall_status = "unhealthy"
    else:
        overall_status = "degraded"

    unhealthy_modules = [
        _serialize_module(row)
        for row in modules
        if str(row.health_status or "unknown") != "healthy"
    ]

    return {
        "overall_status": overall_status,
        "modules": [_serialize_module(row) for row in modules],
        "tasks": [_serialize_task(row) for row in tasks],
        "queue_depths": queue_depths,
        "unhealthy_modules": unhealthy_modules,
    }


__all__ = ["get_service_dashboard", "run_health_checks", "update_task_stats"]
