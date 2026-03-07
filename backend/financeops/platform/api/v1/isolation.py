from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, require_finance_leader
from financeops.db.models.users import IamUser
from financeops.platform.schemas.isolation import IsolationPolicyCreate
from financeops.platform.services.isolation.routing_service import create_isolation_route, resolve_isolation_route

router = APIRouter()


@router.post("/tenants/{tenant_id}")
async def create_route_endpoint(
    tenant_id: uuid.UUID,
    body: IsolationPolicyCreate,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> dict:
    row = await create_isolation_route(
        session,
        tenant_id=tenant_id,
        isolation_tier=body.isolation_tier,
        db_cluster=body.db_cluster,
        schema_name=body.schema_name,
        worker_pool=body.worker_pool,
        region=body.region,
        migration_state=body.migration_state,
        route_version=body.route_version,
        effective_from=body.effective_from,
        effective_to=body.effective_to,
        actor_user_id=user.id,
        correlation_id=str(getattr(request.state, "correlation_id", "") or ""),
    )
    await session.commit()
    return {"id": str(row.id), "route_version": row.route_version}


@router.get("/tenants/{tenant_id}")
async def resolve_route_endpoint(
    tenant_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> dict:
    del user
    row = await resolve_isolation_route(session, tenant_id=tenant_id)
    return {
        "id": str(row.id),
        "db_cluster": row.db_cluster,
        "schema_name": row.schema_name,
        "worker_pool": row.worker_pool,
        "region": row.region,
        "route_version": row.route_version,
        "migration_state": row.migration_state,
    }
