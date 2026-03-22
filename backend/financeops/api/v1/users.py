from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, require_finance_leader
from financeops.core.exceptions import NotFoundError, ValidationError
from financeops.db.models.users import IamUser
from financeops.services.user_service import offboard_user

router = APIRouter()


class OffboardUserRequest(BaseModel):
    reason: str


@router.post("/users/{user_id}/offboard", status_code=status.HTTP_200_OK)
async def offboard_user_endpoint(
    user_id: uuid.UUID,
    body: OffboardUserRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> dict:
    try:
        return await offboard_user(
            session=session,
            tenant_id=user.tenant_id,
            user_id=user_id,
            offboarded_by=user.id,
            reason=body.reason,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail="User not found") from exc
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc

