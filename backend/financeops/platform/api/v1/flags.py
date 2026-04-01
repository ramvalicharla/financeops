from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user
from financeops.db.models.users import IamUser, UserRole
from financeops.platform.db.models.feature_flags import CpModuleFeatureFlag
from financeops.platform.schemas.feature_flags import (
    FeatureFlagCreate,
    FeatureFlagEvaluationRequest,
)
from financeops.platform.services.feature_flags.flag_service import (
    create_feature_flag,
    evaluate_feature_flag,
)

router = APIRouter()

_PLATFORM_ADMIN_ROLES = {
    UserRole.super_admin,
    UserRole.platform_owner,
    UserRole.platform_admin,
}


def _require_platform_admin(user: IamUser) -> IamUser:
    if user.role not in _PLATFORM_ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="platform_admin role required")
    return user


class FeatureFlagUpdateRequest(BaseModel):
    rollout_mode: str | None = Field(default=None, pattern="^(off|on|canary)$")
    compute_enabled: bool | None = None
    write_enabled: bool | None = None
    visibility_enabled: bool | None = None
    traffic_percent: float | None = Field(default=None, ge=0, le=100)
    effective_to: datetime | None = None
    enabled: bool | None = None


def _serialize_flag(row: CpModuleFeatureFlag) -> dict:
    return {
        "id": str(row.id),
        "tenant_id": str(row.tenant_id),
        "module_id": str(row.module_id),
        "flag_key": row.flag_key,
        "flag_value": row.flag_value,
        "rollout_mode": row.rollout_mode,
        "compute_enabled": row.compute_enabled,
        "write_enabled": row.write_enabled,
        "visibility_enabled": row.visibility_enabled,
        "target_scope_type": row.target_scope_type,
        "target_scope_id": str(row.target_scope_id) if row.target_scope_id else None,
        "traffic_percent": float(row.traffic_percent or 0.0)
        if row.traffic_percent is not None
        else None,
        "effective_from": row.effective_from.isoformat(),
        "effective_to": row.effective_to.isoformat() if row.effective_to else None,
    }


@router.get("")
async def list_feature_flags_endpoint(
    tenant_id: uuid.UUID | None = Query(default=None),
    module_id: uuid.UUID | None = Query(default=None),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    _require_platform_admin(user)
    target_tenant_id = tenant_id or user.tenant_id
    stmt = select(CpModuleFeatureFlag).where(
        CpModuleFeatureFlag.tenant_id == target_tenant_id
    )
    if module_id is not None:
        stmt = stmt.where(CpModuleFeatureFlag.module_id == module_id)
    rows = (
        await session.execute(
            stmt.order_by(
                CpModuleFeatureFlag.effective_from.desc(),
                CpModuleFeatureFlag.id.desc(),
            )
        )
    ).scalars().all()
    return [_serialize_flag(row) for row in rows]


@router.post("/tenants/{tenant_id}")
async def create_feature_flag_endpoint(
    tenant_id: uuid.UUID,
    body: FeatureFlagCreate,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    _require_platform_admin(user)
    row = await create_feature_flag(
        session,
        tenant_id=tenant_id,
        module_id=body.module_id,
        flag_key=body.flag_key,
        flag_value=body.flag_value,
        rollout_mode=body.rollout_mode,
        compute_enabled=body.compute_enabled,
        write_enabled=body.write_enabled,
        visibility_enabled=body.visibility_enabled,
        target_scope_type=body.target_scope_type,
        target_scope_id=body.target_scope_id,
        traffic_percent=body.traffic_percent,
        effective_from=body.effective_from,
        effective_to=body.effective_to,
        actor_user_id=user.id,
        correlation_id=str(getattr(request.state, "correlation_id", "") or ""),
    )
    await session.commit()
    return {"id": str(row.id), "flag_key": row.flag_key}


@router.put("/{flag_id}")
async def update_feature_flag_endpoint(
    flag_id: uuid.UUID,
    body: FeatureFlagUpdateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    _require_platform_admin(user)
    row = (
        await session.execute(
            select(CpModuleFeatureFlag).where(
                CpModuleFeatureFlag.id == flag_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="feature flag not found")

    if body.enabled is not None:
        row.rollout_mode = "on" if body.enabled else "off"
    if body.rollout_mode is not None:
        row.rollout_mode = body.rollout_mode
    if body.compute_enabled is not None:
        row.compute_enabled = body.compute_enabled
    if body.write_enabled is not None:
        row.write_enabled = body.write_enabled
    if body.visibility_enabled is not None:
        row.visibility_enabled = body.visibility_enabled
    if body.traffic_percent is not None:
        row.traffic_percent = body.traffic_percent
    if body.effective_to is not None:
        row.effective_to = body.effective_to

    await session.commit()
    return _serialize_flag(row)


@router.delete("/{flag_id}")
async def delete_feature_flag_endpoint(
    flag_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    _require_platform_admin(user)
    row = (
        await session.execute(
            select(CpModuleFeatureFlag).where(
                CpModuleFeatureFlag.id == flag_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="feature flag not found")

    await session.delete(row)
    await session.commit()
    return {"deleted": True, "id": str(flag_id), "deleted_at": datetime.now(UTC).isoformat()}


@router.post("/evaluate")
async def evaluate_feature_flag_endpoint(
    body: FeatureFlagEvaluationRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    _require_platform_admin(user)
    return await evaluate_feature_flag(
        session,
        tenant_id=user.tenant_id,
        module_id=body.module_id,
        flag_key=body.flag_key,
        request_fingerprint=body.request_fingerprint,
        user_id=body.user_id or user.id,
        entity_id=body.entity_id,
    )
