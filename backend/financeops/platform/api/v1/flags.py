from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, require_finance_leader
from financeops.db.models.users import IamUser
from financeops.platform.schemas.feature_flags import (
    FeatureFlagCreate,
    FeatureFlagEvaluationRequest,
)
from financeops.platform.services.feature_flags.flag_service import create_feature_flag, evaluate_feature_flag

router = APIRouter()


@router.post("/tenants/{tenant_id}")
async def create_feature_flag_endpoint(
    tenant_id: uuid.UUID,
    body: FeatureFlagCreate,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> dict:
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


@router.post("/evaluate")
async def evaluate_feature_flag_endpoint(
    body: FeatureFlagEvaluationRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> dict:
    return await evaluate_feature_flag(
        session,
        tenant_id=user.tenant_id,
        module_id=body.module_id,
        flag_key=body.flag_key,
        request_fingerprint=body.request_fingerprint,
        user_id=body.user_id or user.id,
        entity_id=body.entity_id,
    )
