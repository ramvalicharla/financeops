from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, Query
from celery.result import AsyncResult
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user, require_finance_leader
from financeops.core.intent.dispatcher import JobDispatcher
from financeops.db.models.users import IamUser
from financeops.modules.search.service import search
from financeops.modules.search.tasks import reindex_search_index
from financeops.tasks.celery_app import celery_app

router = APIRouter(prefix="/search", tags=["search"])
log = logging.getLogger(__name__)


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
    del session
    task_id: str
    try:
        task = JobDispatcher().enqueue_task(
            reindex_search_index,
            tenant_id=str(user.tenant_id),
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
