from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, require_finance_team
from financeops.db.models.users import IamUser
from financeops.platform.services.tenancy.entity_access import (
    get_entities_for_user,
    get_entity_for_user,
)

router = APIRouter()


@router.get("")
async def list_entities_endpoint(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> list[dict]:
    entities = await get_entities_for_user(
        session=session,
        tenant_id=user.tenant_id,
        user_id=user.id,
        user_role=user.role,
    )
    return [
        {
            "id": str(item.id),
            "entity_code": item.entity_code,
            "entity_name": item.entity_name,
            "organisation_id": str(item.organisation_id),
            "pan": item.pan,
            "tan": item.tan,
            "cin": item.cin,
            "gstin": item.gstin,
            "lei": item.lei,
            "fiscal_year_start": item.fiscal_year_start,
            "applicable_gaap": item.applicable_gaap,
            "tax_rate": str(item.tax_rate) if item.tax_rate is not None else None,
            "state_code": item.state_code,
            "registered_address": item.registered_address,
            "city": item.city,
            "pincode": item.pincode,
        }
        for item in entities
    ]


@router.get("/{entity_id}")
async def get_entity_endpoint(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict:
    item = await get_entity_for_user(
        session=session,
        tenant_id=user.tenant_id,
        entity_id=entity_id,
        user_id=user.id,
        user_role=user.role,
    )
    return {
        "id": str(item.id),
        "entity_code": item.entity_code,
        "entity_name": item.entity_name,
        "organisation_id": str(item.organisation_id),
        "pan": item.pan,
        "tan": item.tan,
        "cin": item.cin,
        "gstin": item.gstin,
        "lei": item.lei,
        "fiscal_year_start": item.fiscal_year_start,
        "applicable_gaap": item.applicable_gaap,
        "tax_rate": str(item.tax_rate) if item.tax_rate is not None else None,
        "state_code": item.state_code,
        "registered_address": item.registered_address,
        "city": item.city,
        "pincode": item.pincode,
    }
