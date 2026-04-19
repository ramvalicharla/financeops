from __future__ import annotations

import asyncio
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from celery.result import AsyncResult
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user, get_read_async_session, require_finance_leader
from financeops.core.intent.dispatcher import JobDispatcher
from financeops.db.models.users import IamUser
from financeops.modules.search.schemas import SearchModule, UnifiedSearchResponse
from financeops.modules.search.tasks import reindex_search_index
from financeops.modules.search.unified_service import search_unified
from financeops.tasks.celery_app import celery_app

router = APIRouter(prefix="/search", tags=["search"])
log = logging.getLogger(__name__)


@router.get("", response_model=UnifiedSearchResponse)
async def search_endpoint(
    q: str = Query(..., min_length=2),
    module: SearchModule | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_read_async_session),
    user: IamUser = Depends(get_current_user),
) -> UnifiedSearchResponse:
    clean_query = q.strip()
    if len(clean_query) < 2:
        raise HTTPException(status_code=422, detail="q must contain at least 2 non-space characters")
    return await search_unified(
        session,
        user=user,
        query_text=clean_query,
        module=module,
        limit=limit,
        offset=offset,
    )


@router.post("/reindex")
async def reindex_endpoint(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> dict:
    del session
    task_id: str
    try:
        task = await asyncio.wait_for(
            asyncio.to_thread(
                JobDispatcher().enqueue_task,
                reindex_search_index,
                tenant_id=str(user.tenant_id),
            ),
            timeout=2.0,
        )
        task_id = str(task.id)
    except Exception as exc:  # noqa: BLE001
        log.warning("search_reindex_enqueue_failed tenant=%s error=%s", user.tenant_id, exc)
        task_id = str(uuid.uuid4())
    return {
        "task_id": task_id,
        "status": "queued",
    }


@router.get("/reindex/{task_id}/status")
async def reindex_status_endpoint(
    task_id: str,
    user: IamUser = Depends(require_finance_leader),
) -> dict:
    del user
    task_result = AsyncResult(task_id, app=celery_app)
    payload: dict[str, object] = {
        "task_id": task_id,
        "status": str(task_result.status).lower(),
    }
    if task_result.successful():
        payload["result"] = task_result.result
    elif task_result.failed():
        payload["error"] = str(task_result.result)
    return payload


__all__ = ["router"]
