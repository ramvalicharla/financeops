from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, require_finance_leader
from financeops.db.models.users import IamUser
from financeops.platform.schemas.quotas import QuotaAssignmentCreate, QuotaCheckRequest
from financeops.platform.services.quotas.policy_service import assign_quota_to_tenant
from financeops.platform.services.quotas.quota_guard import QuotaGuard, QuotaGuardRequest

router = APIRouter()


@router.post("/tenants/{tenant_id}/assignments")
async def assign_quota_endpoint(
    tenant_id: uuid.UUID,
    body: QuotaAssignmentCreate,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> dict:
    row = await assign_quota_to_tenant(
        session,
        tenant_id=tenant_id,
        quota_type=body.quota_type,
        window_type=body.window_type,
        window_seconds=body.window_seconds,
        max_value=body.max_value,
        enforcement_mode=body.enforcement_mode,
        effective_from=body.effective_from,
        effective_to=body.effective_to,
        actor_user_id=user.id,
        correlation_id=str(getattr(request.state, "correlation_id", "") or ""),
    )
    await session.commit()
    return {"id": str(row.id), "quota_type": row.quota_type}


@router.post("/check")
async def quota_check_endpoint(
    body: QuotaCheckRequest,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> dict:
    result = await QuotaGuard.check_and_record(
        session,
        QuotaGuardRequest(
            tenant_id=user.tenant_id,
            quota_type=body.quota_type,
            usage_delta=body.usage_delta,
            operation_id=body.operation_id or uuid.uuid4(),
            idempotency_key=body.idempotency_key,
            request_fingerprint=body.request_fingerprint,
            source_layer=body.source_layer,
            actor_user_id=user.id,
            correlation_id=str(getattr(request.state, "correlation_id", "") or ""),
        ),
    )
    await session.commit()
    return result
