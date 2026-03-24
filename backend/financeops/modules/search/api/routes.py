from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user, require_finance_leader
from financeops.db.models.users import IamUser
from financeops.modules.search.service import reindex_tenant, search

router = APIRouter(prefix="/search", tags=["search"])


@router.get("")
async def search_endpoint(
    q: str = Query(default=""),
    types: str | None = Query(default=None),
    limit: int = Query(default=10, ge=1, le=20),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    parsed_types = [value.strip() for value in (types or "").split(",") if value.strip()]
    rows = await search(
        session,
        tenant_id=user.tenant_id,
        query=q,
        entity_types=parsed_types or None,
        limit=limit,
    )
    return rows


@router.post("/reindex")
async def reindex_endpoint(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> dict:
    try:
        counts = await reindex_tenant(session, tenant_id=user.tenant_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {
        "task_id": str(uuid.uuid4()),
        "status": "queued",
        "counts": counts,
    }


__all__ = ["router"]

