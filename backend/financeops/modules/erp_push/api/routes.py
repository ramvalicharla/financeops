from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user
from financeops.db.models.erp_push import ErpPushRun
from financeops.db.models.users import IamUser
from financeops.modules.erp_push.application.posting_service import execute_push
from financeops.modules.erp_push.application.push_task import push_journal_task
from financeops.shared_kernel.response import ok

router = APIRouter(tags=["ERP Push"])


class PushRequest(BaseModel):
    connection_id: uuid.UUID
    connector_type: str
    simulation: bool = False


class PushStatusResponse(BaseModel):
    jv_id: uuid.UUID
    status: str
    external_journal_id: str | None
    error_code: str | None
    error_category: str | None
    attempt_number: int


class AsyncPushResponse(BaseModel):
    task_id: str
    jv_id: uuid.UUID
    connector_type: str
    status: str = "QUEUED"


@router.post("/jv/{jv_id}/push")
async def push_jv_endpoint(
    request: Request,
    jv_id: uuid.UUID,
    body: PushRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    run = await execute_push(
        session,
        jv_id=jv_id,
        tenant_id=user.tenant_id,
        connection_id=body.connection_id,
        connector_type=body.connector_type,
        simulation=body.simulation,
    )
    await session.flush()
    payload = PushStatusResponse(
        jv_id=jv_id,
        status=run.status,
        external_journal_id=run.external_journal_id,
        error_code=run.error_code,
        error_category=run.error_category,
        attempt_number=run.attempt_number,
    ).model_dump(mode="json")
    return ok(payload, request_id=getattr(request.state, "request_id", None)).model_dump(mode="json")


@router.post("/jv/{jv_id}/push-async")
async def push_jv_async_endpoint(
    request: Request,
    jv_id: uuid.UUID,
    body: PushRequest,
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    task = push_journal_task.apply_async(
        kwargs={
            "jv_id": str(jv_id),
            "tenant_id": str(user.tenant_id),
            "connection_id": str(body.connection_id),
            "connector_type": body.connector_type,
            "simulation": body.simulation,
        },
        queue="high_q",
    )
    payload = AsyncPushResponse(
        task_id=task.id,
        jv_id=jv_id,
        connector_type=body.connector_type,
    ).model_dump(mode="json")
    return ok(payload, request_id=getattr(request.state, "request_id", None)).model_dump(mode="json")


@router.get("/jv/{jv_id}/push-status")
async def get_push_status_endpoint(
    request: Request,
    jv_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    rows = (
        await session.execute(
            select(ErpPushRun)
            .where(
                ErpPushRun.jv_id == jv_id,
                ErpPushRun.tenant_id == user.tenant_id,
            )
            .order_by(ErpPushRun.created_at.desc())
        )
    ).scalars().all()

    payload = [
        PushStatusResponse(
            jv_id=jv_id,
            status=row.status,
            external_journal_id=row.external_journal_id,
            error_code=row.error_code,
            error_category=row.error_category,
            attempt_number=row.attempt_number,
        ).model_dump(mode="json")
        for row in rows
    ]
    return ok(payload, request_id=getattr(request.state, "request_id", None)).model_dump(mode="json")
