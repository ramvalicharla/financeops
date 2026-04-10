from __future__ import annotations

from decimal import Decimal

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user
from financeops.db.models.users import IamUser, UserRole
from financeops.platform.db.models.entities import CpEntity
from financeops.modules.service_registry.models import ModuleRegistry, TaskRegistry
from financeops.modules.service_registry.service import (
    detect_dependency_cycles,
    ensure_registry_seeded,
    get_service_dashboard,
    run_health_checks,
)
from financeops.shared_kernel.pagination import Paginated

router = APIRouter(prefix="/platform/services", tags=["service-registry"])


class ModuleToggleRequest(BaseModel):
    is_enabled: bool


class ModuleToggleValidationRequest(BaseModel):
    is_enabled: bool
    entity_id: uuid.UUID | None = None


class ModuleToggleValidationResponse(BaseModel):
    success: bool
    failure: bool
    reason: str | None
    module_name: str
    entity_id: str | None


def _require_platform_admin(user: IamUser) -> IamUser:
    if user.role not in {
        UserRole.super_admin,
        UserRole.platform_owner,
        UserRole.platform_admin,
    }:
        raise HTTPException(status_code=403, detail="platform_admin role required")
    return user


def _require_platform_owner(user: IamUser) -> IamUser:
    if user.role not in {UserRole.super_admin, UserRole.platform_owner}:
        raise HTTPException(status_code=403, detail="platform_owner role required")
    return user


def _serialize_module(row: ModuleRegistry) -> dict:
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


def _serialize_task(row: TaskRegistry) -> dict:
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


@router.get("/dashboard")
async def dashboard_endpoint(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    _require_platform_admin(user)
    return await get_service_dashboard(session)


@router.post("/health-check")
async def health_check_endpoint(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    _require_platform_admin(user)
    return await run_health_checks(session)


@router.get("/modules", response_model=Paginated[dict])
async def list_modules_endpoint(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> Paginated[dict]:
    _require_platform_admin(user)
    await ensure_registry_seeded(session)
    stmt = select(ModuleRegistry)
    total = int((await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one())
    rows = (
        await session.execute(
            stmt.order_by(ModuleRegistry.module_name.asc()).offset(offset).limit(limit)
        )
    ).scalars().all()
    return Paginated[dict](
        data=[_serialize_module(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/tasks", response_model=Paginated[dict])
async def list_tasks_endpoint(
    queue_name: str | None = Query(default=None),
    is_scheduled: bool | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> Paginated[dict]:
    _require_platform_admin(user)
    await ensure_registry_seeded(session)
    stmt = select(TaskRegistry)
    if queue_name:
        stmt = stmt.where(TaskRegistry.queue_name == queue_name)
    if is_scheduled is not None:
        stmt = stmt.where(TaskRegistry.is_scheduled.is_(is_scheduled))
    total = int((await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one())
    rows = (
        await session.execute(
            stmt.order_by(TaskRegistry.task_name.asc()).offset(offset).limit(limit)
        )
    ).scalars().all()
    return Paginated[dict](
        data=[_serialize_task(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.patch("/modules/{module_name}/toggle")
async def toggle_module_endpoint(
    module_name: str,
    body: ModuleToggleRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    _require_platform_owner(user)
    await ensure_registry_seeded(session)
    row = (
        await session.execute(
            select(ModuleRegistry).where(ModuleRegistry.module_name == module_name)
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="module not found")
    if body.is_enabled:
        rows = (
            await session.execute(select(ModuleRegistry).order_by(ModuleRegistry.module_name.asc()))
        ).scalars().all()
        dependency_cycles = detect_dependency_cycles(list(rows))
        cyclic_modules = {name for cycle in dependency_cycles for name in cycle}
        if row.module_name in cyclic_modules:
            raise HTTPException(
                status_code=409,
                detail="module dependency cycle detected; enable blocked",
            )

    row.is_enabled = body.is_enabled
    await session.flush()
    return _serialize_module(row)


@router.post("/modules/{module_name}/toggle/validate", response_model=ModuleToggleValidationResponse)
async def validate_toggle_module_endpoint(
    module_name: str,
    body: ModuleToggleValidationRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> ModuleToggleValidationResponse:
    _require_platform_owner(user)
    await ensure_registry_seeded(session)
    row = (
        await session.execute(
            select(ModuleRegistry).where(ModuleRegistry.module_name == module_name)
        )
    ).scalar_one_or_none()
    if row is None:
        return ModuleToggleValidationResponse(
            success=False,
            failure=True,
            reason="Module is not registered in the current backend contract.",
            module_name=module_name,
            entity_id=str(body.entity_id) if body.entity_id else None,
        )

    rows = (
        await session.execute(select(ModuleRegistry).order_by(ModuleRegistry.module_name.asc()))
    ).scalars().all()
    dependency_cycles = detect_dependency_cycles(list(rows))
    cyclic_modules = {name for cycle in dependency_cycles for name in cycle}
    if body.is_enabled and row.module_name in cyclic_modules:
        return ModuleToggleValidationResponse(
            success=False,
            failure=True,
            reason="Module dependency cycle detected; enable blocked until registry graph is acyclic.",
            module_name=row.module_name,
            entity_id=str(body.entity_id) if body.entity_id else None,
        )

    if body.is_enabled and body.entity_id is not None:
        entity_filters = [CpEntity.id == body.entity_id, CpEntity.deactivated_at.is_(None)]
        if user.role not in {UserRole.super_admin, UserRole.platform_owner, UserRole.platform_admin}:
            entity_filters.append(CpEntity.tenant_id == user.tenant_id)
        entity = (
            await session.execute(
                select(CpEntity.id).where(
                    *entity_filters,
                )
            )
        ).scalar_one_or_none()
        if entity is None:
            return ModuleToggleValidationResponse(
                success=False,
                failure=True,
                reason="Select an active entity before enabling a module during onboarding.",
                module_name=row.module_name,
                entity_id=str(body.entity_id),
            )

    if body.is_enabled and row.health_status == "unhealthy":
        return ModuleToggleValidationResponse(
            success=False,
            failure=True,
            reason="Module cannot be enabled while backend health is unhealthy.",
            module_name=row.module_name,
            entity_id=str(body.entity_id) if body.entity_id else None,
        )

    return ModuleToggleValidationResponse(
        success=True,
        failure=False,
        reason=None,
        module_name=row.module_name,
        entity_id=str(body.entity_id) if body.entity_id else None,
    )


__all__ = ["router"]
