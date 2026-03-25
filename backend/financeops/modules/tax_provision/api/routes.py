from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user
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
    row = await compute_tax_provision(
        session,
        tenant_id=user.tenant_id,
        period=body.period,
        entity_id=body.entity_id,
        applicable_tax_rate=body.applicable_tax_rate,
        created_by=user.id,
        requester_user_id=user.id,
        requester_user_role=user.role.value,
    )
    return _serialize_provision(row)


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
    body: UpsertTaxPositionRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    row = await upsert_tax_position(
        session,
        tenant_id=user.tenant_id,
        position_name=body.position_name,
        position_type=body.position_type,
        carrying_amount=body.carrying_amount,
        tax_base=body.tax_base,
        is_asset=body.is_asset,
        tax_rate=body.tax_rate,
        description=body.description,
    )
    return _serialize_position(row)


__all__ = ["router"]
