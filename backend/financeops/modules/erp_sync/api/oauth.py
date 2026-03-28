from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user
from financeops.db.models.users import IamUser
from financeops.modules.erp_sync.application.oauth_service import consume_oauth_callback, start_oauth_session
from financeops.shared_kernel.response import ok

router = APIRouter(prefix="/connections/{connection_id}/oauth")


class OAuthStartRequest(BaseModel):
    redirect_uri: str = Field(..., min_length=1)
    entity_id: uuid.UUID | None = None
    scopes: str | None = None


@router.post("/start")
async def oauth_start(
    request: Request,
    connection_id: uuid.UUID,
    body: OAuthStartRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    result = await start_oauth_session(
        session,
        tenant_id=user.tenant_id,
        connection_id=connection_id,
        entity_id=body.entity_id,
        redirect_uri=body.redirect_uri,
        initiated_by_user_id=user.id,
        scopes=body.scopes,
    )
    await session.flush()
    return ok(result, request_id=getattr(request.state, "request_id", None)).model_dump(mode="json")


@router.get("/callback")
async def oauth_callback(
    request: Request,
    connection_id: uuid.UUID,
    state: str = Query(...),
    code: str = Query(...),
    realm_id: str | None = Query(default=None, alias="realmId"),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    result = await consume_oauth_callback(
        session,
        tenant_id=user.tenant_id,
        connection_id=connection_id,
        state_token=state,
        code=code,
        initiated_by_user_id=user.id,
        realm_id=realm_id,
    )
    await session.flush()
    return ok(result, request_id=getattr(request.state, "request_id", None)).model_dump(mode="json")
