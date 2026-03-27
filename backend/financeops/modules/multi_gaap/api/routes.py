from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user
from financeops.db.models.users import IamUser
from financeops.modules.multi_gaap.models import MultiGAAPConfig, MultiGAAPRun
from financeops.modules.multi_gaap.service import compute_gaap_view, get_gaap_comparison, get_or_create_config, get_specific_run, update_config
from financeops.platform.services.tenancy.entity_access import assert_entity_access, get_entities_for_user

router = APIRouter(prefix="/gaap", tags=["gaap"])


class ConfigPatchRequest(BaseModel):
    primary_gaap: str | None = None
    secondary_gaaps: list[str] | None = None
    revenue_recognition_policy: dict | None = None
    lease_classification_policy: dict | None = None
    financial_instruments_policy: dict | None = None


class ComputeRequest(BaseModel):
    entity_id: uuid.UUID | None = None
    period: str
    gaap_framework: str


def _decimal(value: Decimal) -> str:
    return format(Decimal(str(value)), "f")


def _serialize_config(row: MultiGAAPConfig) -> dict:
    return {
        "id": str(row.id),
        "tenant_id": str(row.tenant_id),
        "entity_id": str(row.entity_id),
        "primary_gaap": row.primary_gaap,
        "secondary_gaaps": row.secondary_gaaps or [],
        "revenue_recognition_policy": row.revenue_recognition_policy or {},
        "lease_classification_policy": row.lease_classification_policy or {},
        "financial_instruments_policy": row.financial_instruments_policy or {},
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


def _serialize_run(row: MultiGAAPRun) -> dict:
    return {
        "id": str(row.id),
        "entity_id": str(row.entity_id),
        "period": row.period,
        "gaap_framework": row.gaap_framework,
        "revenue": _decimal(row.revenue),
        "gross_profit": _decimal(row.gross_profit),
        "ebitda": _decimal(row.ebitda),
        "ebit": _decimal(row.ebit),
        "profit_before_tax": _decimal(row.profit_before_tax),
        "profit_after_tax": _decimal(row.profit_after_tax),
        "total_assets": _decimal(row.total_assets),
        "total_equity": _decimal(row.total_equity),
        "adjustments": row.adjustments or [],
        "created_by": str(row.created_by),
        "created_at": row.created_at.isoformat(),
    }


async def _resolve_entity_id(
    session: AsyncSession,
    user: IamUser,
    entity_id: uuid.UUID | None,
) -> uuid.UUID:
    if entity_id is not None:
        return entity_id
    entities = await get_entities_for_user(
        session=session,
        tenant_id=user.tenant_id,
        user_id=user.id,
        user_role=user.role,
    )
    if entities:
        return entities[0].id
    raise HTTPException(status_code=422, detail="entity_id is required because no entity is configured for this user")


@router.get("/config")
async def get_config_endpoint(
    entity_id: uuid.UUID | None = None,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    resolved_entity_id = await _resolve_entity_id(session, user, entity_id)
    await assert_entity_access(session, user.tenant_id, resolved_entity_id, user.id, user.role)
    row = await get_or_create_config(session, tenant_id=user.tenant_id, entity_id=resolved_entity_id)
    return _serialize_config(row)


@router.patch("/config")
async def patch_config_endpoint(
    body: ConfigPatchRequest,
    entity_id: uuid.UUID | None = None,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    resolved_entity_id = await _resolve_entity_id(session, user, entity_id)
    await assert_entity_access(session, user.tenant_id, resolved_entity_id, user.id, user.role)
    row = await update_config(
        session,
        tenant_id=user.tenant_id,
        updates=body.model_dump(exclude_none=True),
        entity_id=resolved_entity_id,
    )
    return _serialize_config(row)


@router.post("/compute")
async def compute_endpoint(
    body: ComputeRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    resolved_entity_id = await _resolve_entity_id(session, user, body.entity_id)
    await assert_entity_access(session, user.tenant_id, resolved_entity_id, user.id, user.role)
    row = await compute_gaap_view(
        session,
        tenant_id=user.tenant_id,
        period=body.period,
        gaap_framework=body.gaap_framework,
        created_by=user.id,
        entity_id=resolved_entity_id,
    )
    return _serialize_run(row)


@router.get("/comparison")
async def comparison_endpoint(
    period: str,
    entity_id: uuid.UUID | None = None,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    resolved_entity_id = await _resolve_entity_id(session, user, entity_id)
    await assert_entity_access(session, user.tenant_id, resolved_entity_id, user.id, user.role)
    payload = await get_gaap_comparison(
        session,
        tenant_id=user.tenant_id,
        period=period,
        entity_id=resolved_entity_id,
    )
    return {
        "period": payload["period"],
        "frameworks": [
            {
                "gaap_framework": row["gaap_framework"],
                "revenue": _decimal(row["revenue"]),
                "gross_profit": _decimal(row["gross_profit"]),
                "ebitda": _decimal(row["ebitda"]),
                "profit_before_tax": _decimal(row["profit_before_tax"]),
                "profit_after_tax": _decimal(row["profit_after_tax"]),
                "adjustments": row["adjustments"],
            }
            for row in payload["frameworks"]
        ],
        "differences": {
            key: {sub_key: _decimal(sub_val) for sub_key, sub_val in value.items()}
            for key, value in payload["differences"].items()
        },
    }


@router.get("/{gaap_framework}/{period}")
async def get_specific_endpoint(
    gaap_framework: str,
    period: str,
    entity_id: uuid.UUID | None = None,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    try:
        resolved_entity_id = await _resolve_entity_id(session, user, entity_id)
    except HTTPException as exc:
        if exc.status_code == 422:
            raise HTTPException(status_code=404, detail="GAAP run not found") from exc
        raise
    await assert_entity_access(session, user.tenant_id, resolved_entity_id, user.id, user.role)
    row = await get_specific_run(
        session,
        tenant_id=user.tenant_id,
        gaap_framework=gaap_framework,
        period=period,
        entity_id=resolved_entity_id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="GAAP run not found")
    return _serialize_run(row)


__all__ = ["router"]
