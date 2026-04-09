from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user
from financeops.core.intent.api import build_idempotency_key, build_intent_actor
from financeops.core.intent.enums import IntentType
from financeops.core.intent.service import IntentService
from financeops.db.models.users import IamUser
from financeops.modules.tax_provision.models import TaxPosition, TaxProvisionRun
from financeops.modules.tax_provision.service import (
    compute_tax_provision,
    get_provision_for_period,
    get_tax_provision_schedule,
    list_tax_positions,
    upsert_tax_position,
)
from financeops.platform.services.tenancy.entity_access import assert_entity_access
from financeops.shared_kernel.pagination import Paginated

router = APIRouter(prefix="/tax", tags=["tax"])


async def _submit_intent(
    request: Request,
    session: AsyncSession,
    *,
    user: IamUser,
    intent_type: IntentType,
    payload: dict,
    target_id: uuid.UUID | None = None,
):
    return await IntentService(session).submit_intent(
        intent_type=intent_type,
        actor=build_intent_actor(request, user),
        payload=payload,
        idempotency_key=build_idempotency_key(
            request,
            intent_type=intent_type,
            actor=user,
            body=payload,
            target_id=target_id,
        ),
        target_id=target_id,
    )


class ComputeProvisionRequest(BaseModel):
    period: str
    entity_id: uuid.UUID | None = None
    applicable_tax_rate: Decimal
    tax_rate_description: str | None = None


class UpsertTaxPositionRequest(BaseModel):
    position_name: str
    position_type: str
    carrying_amount: Decimal
    tax_base: Decimal
    is_asset: bool
    tax_rate: Decimal = Decimal("0.2500")
    description: str | None = None


def _decimal(value: Decimal) -> str:
    return format(Decimal(str(value)), "f")


def _serialize_provision(row: TaxProvisionRun) -> dict:
    return {
        "id": str(row.id),
        "period": row.period,
        "fiscal_year": row.fiscal_year,
        "applicable_tax_rate": _decimal(row.applicable_tax_rate),
        "accounting_profit_before_tax": _decimal(row.accounting_profit_before_tax),
        "permanent_differences": _decimal(row.permanent_differences),
        "timing_differences": _decimal(row.timing_differences),
        "taxable_income": _decimal(row.taxable_income),
        "current_tax_expense": _decimal(row.current_tax_expense),
        "deferred_tax_asset": _decimal(row.deferred_tax_asset),
        "deferred_tax_liability": _decimal(row.deferred_tax_liability),
        "net_deferred_tax": _decimal(row.net_deferred_tax),
        "total_tax_expense": _decimal(row.total_tax_expense),
        "effective_tax_rate": _decimal(row.effective_tax_rate),
        "created_by": str(row.created_by),
        "created_at": row.created_at.isoformat(),
    }


def _serialize_position(row: TaxPosition) -> dict:
    return {
        "id": str(row.id),
        "tenant_id": str(row.tenant_id),
        "position_name": row.position_name,
        "position_type": row.position_type,
        "carrying_amount": _decimal(row.carrying_amount),
        "tax_base": _decimal(row.tax_base),
        "temporary_difference": _decimal(row.temporary_difference),
        "deferred_tax_impact": _decimal(row.deferred_tax_impact),
        "is_asset": row.is_asset,
        "description": row.description,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


@router.post("/provision/compute")
async def compute_provision_endpoint(
    request: Request,
    body: ComputeProvisionRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    await assert_entity_access(
        session=session,
        tenant_id=user.tenant_id,
        entity_id=body.entity_id,
        user_id=user.id,
        user_role=user.role,
    )
    result = await _submit_intent(
        request,
        session,
        user=user,
        intent_type=IntentType.COMPUTE_TAX_PROVISION,
        payload={
            "period": body.period,
            "entity_id": str(body.entity_id) if body.entity_id else None,
            "applicable_tax_rate": str(body.applicable_tax_rate),
        },
    )
    row = await get_provision_for_period(session, tenant_id=user.tenant_id, period=body.period)
    payload = _serialize_provision(row)
    payload["intent_id"] = str(result.intent_id)
    payload["job_id"] = str(result.job_id) if result.job_id else None
    return payload


@router.get("/provision/{period}")
async def get_provision_endpoint(
    period: str,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    row = await get_provision_for_period(session, tenant_id=user.tenant_id, period=period)
    return _serialize_provision(row)


@router.get("/schedule")
async def get_schedule_endpoint(
    fiscal_year: int,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    payload = await get_tax_provision_schedule(session, tenant_id=user.tenant_id, fiscal_year=fiscal_year)
    return {
        "fiscal_year": payload["fiscal_year"],
        "periods": [_serialize_provision(row) for row in payload["periods"]],
        "ytd_current_tax": _decimal(payload["ytd_current_tax"]),
        "ytd_deferred_tax": _decimal(payload["ytd_deferred_tax"]),
        "ytd_total_tax": _decimal(payload["ytd_total_tax"]),
        "effective_tax_rate_ytd": _decimal(payload["effective_tax_rate_ytd"]),
        "deferred_tax_positions": [_serialize_position(row) for row in payload["deferred_tax_positions"]],
    }


@router.get("/positions", response_model=Paginated[dict])
async def list_positions_endpoint(
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> Paginated[dict]:
    payload = await list_tax_positions(session, tenant_id=user.tenant_id, limit=limit, offset=offset)
    return Paginated[dict](
        data=[_serialize_position(row) for row in payload["data"]],
        total=payload["total"],
        limit=payload["limit"],
        offset=payload["offset"],
    )


@router.post("/positions")
async def upsert_position_endpoint(
    request: Request,
    body: UpsertTaxPositionRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    result = await _submit_intent(
        request,
        session,
        user=user,
        intent_type=IntentType.UPSERT_TAX_POSITION,
        payload=body.model_dump(mode="json"),
    )
    row = (
        await session.execute(
            select(TaxPosition).where(
                TaxPosition.tenant_id == user.tenant_id,
                TaxPosition.position_name == body.position_name,
            )
        )
    ).scalar_one()
    payload = _serialize_position(row)
    payload["intent_id"] = str(result.intent_id)
    payload["job_id"] = str(result.job_id) if result.job_id else None
    return payload


__all__ = ["router"]
