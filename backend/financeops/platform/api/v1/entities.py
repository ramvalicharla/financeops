from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, require_finance_team
from financeops.db.models.users import IamUser
from financeops.platform.db.models.entities import CpEntity

router = APIRouter()


@router.get("")
async def list_entities_endpoint(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> list[dict]:
    result = await session.execute(
        select(CpEntity)
        .where(CpEntity.tenant_id == user.tenant_id)
        .order_by(CpEntity.entity_code)
    )
    return [
        {
            "id": str(item.id),
            "entity_code": item.entity_code,
            "entity_name": item.entity_name,
            "organisation_id": str(item.organisation_id),
        }
        for item in result.scalars().all()
    ]
