from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, require_finance_leader
from financeops.core.exceptions import NotFoundError, ValidationError
from financeops.db.models.users import IamUser
from financeops.modules.compliance.erasure_service import erase_user_pii, list_erasure_logs
from financeops.modules.compliance.models import ErasureLog
from financeops.shared_kernel.pagination import Paginated

router = APIRouter(prefix="/compliance", tags=["compliance"])


class ErasureRequest(BaseModel):
    user_id: uuid.UUID | None = None
    request_method: str | None = None


class ErasureResponse(BaseModel):
    status: str
    user_id_hash: str
    fields_erased: list[str]
    completed_at: str


class ErasureLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    user_id_hash: str
    requested_by: uuid.UUID | None = None
    request_method: str
    status: str
    pii_fields_erased: list[str]
    completed_at: datetime | None = None
    created_at: datetime


@router.post("/erasure", response_model=ErasureResponse)
async def erasure_endpoint(
    body: ErasureRequest | None = None,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> ErasureResponse:
    payload = body or ErasureRequest()
    target_user_id = payload.user_id or user.id
    if payload.request_method:
        request_method = payload.request_method
    elif target_user_id == user.id:
        request_method = "self"
    else:
        request_method = "admin"

    try:
        result = await erase_user_pii(
            session=session,
            tenant_id=user.tenant_id,
            user_id=target_user_id,
            requested_by=user.id,
            request_method=request_method,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail="User not found") from exc
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc

    return ErasureResponse(**result)


@router.get("/erasure-log", response_model=Paginated[ErasureLogResponse])
async def erasure_log_endpoint(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> Paginated[ErasureLogResponse]:
    rows, total = await list_erasure_logs(
        session=session,
        tenant_id=user.tenant_id,
        limit=limit,
        offset=offset,
    )
    return Paginated[ErasureLogResponse](
        data=[ErasureLogResponse.model_validate(row) for row in rows if isinstance(row, ErasureLog)],
        total=total,
        limit=limit,
        offset=offset,
    )

