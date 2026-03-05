from __future__ import annotations

import logging
from decimal import Decimal

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import (
    get_async_session,
    get_current_user,
    require_finance_team,
)
from financeops.db.models.users import IamUser
from financeops.services.working_capital_service import (
    create_snapshot,
    get_latest_snapshot,
    list_snapshots,
)

log = logging.getLogger(__name__)
router = APIRouter()


class CreateSnapshotRequest(BaseModel):
    period_year: int
    period_month: int
    entity_name: str
    currency: str = "USD"
    # Current assets
    cash_and_equivalents: Decimal = Decimal("0")
    accounts_receivable: Decimal = Decimal("0")
    inventory: Decimal = Decimal("0")
    prepaid_expenses: Decimal = Decimal("0")
    other_current_assets: Decimal = Decimal("0")
    # Current liabilities
    accounts_payable: Decimal = Decimal("0")
    accrued_liabilities: Decimal = Decimal("0")
    short_term_debt: Decimal = Decimal("0")
    other_current_liabilities: Decimal = Decimal("0")
    notes: str | None = None


@router.post("/snapshots", status_code=status.HTTP_201_CREATED)
async def create_wc_snapshot(
    body: CreateSnapshotRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict:
    """Compute and store a working capital snapshot (INSERT ONLY)."""
    snap = await create_snapshot(
        session,
        tenant_id=user.tenant_id,
        period_year=body.period_year,
        period_month=body.period_month,
        entity_name=body.entity_name,
        created_by=user.id,
        cash_and_equivalents=body.cash_and_equivalents,
        accounts_receivable=body.accounts_receivable,
        inventory=body.inventory,
        prepaid_expenses=body.prepaid_expenses,
        other_current_assets=body.other_current_assets,
        accounts_payable=body.accounts_payable,
        accrued_liabilities=body.accrued_liabilities,
        short_term_debt=body.short_term_debt,
        other_current_liabilities=body.other_current_liabilities,
        currency=body.currency,
        notes=body.notes,
    )
    await session.commit()
    return _snapshot_to_dict(snap)


@router.get("/snapshots")
async def list_wc_snapshots(
    entity_name: str | None = None,
    period_year: int | None = None,
    period_month: int | None = None,
    limit: int = 24,
    offset: int = 0,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    """List working capital snapshots."""
    snaps = await list_snapshots(
        session,
        tenant_id=user.tenant_id,
        entity_name=entity_name,
        period_year=period_year,
        period_month=period_month,
        limit=limit,
        offset=offset,
    )
    return {
        "snapshots": [_snapshot_to_dict(s) for s in snaps],
        "count": len(snaps),
    }


@router.get("/snapshots/latest/{entity_name}")
async def get_latest_wc(
    entity_name: str,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    """Get the most recent working capital snapshot for an entity."""
    snap = await get_latest_snapshot(session, user.tenant_id, entity_name)
    if snap is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="No snapshot found for entity")
    return _snapshot_to_dict(snap)


def _snapshot_to_dict(snap) -> dict:
    return {
        "snapshot_id": str(snap.id),
        "period_year": snap.period_year,
        "period_month": snap.period_month,
        "entity_name": snap.entity_name,
        "currency": snap.currency,
        "total_current_assets": str(snap.total_current_assets),
        "total_current_liabilities": str(snap.total_current_liabilities),
        "working_capital": str(snap.working_capital),
        "current_ratio": str(snap.current_ratio),
        "quick_ratio": str(snap.quick_ratio),
        "cash_ratio": str(snap.cash_ratio),
        "cash_and_equivalents": str(snap.cash_and_equivalents),
        "accounts_receivable": str(snap.accounts_receivable),
        "inventory": str(snap.inventory),
        "accounts_payable": str(snap.accounts_payable),
        "chain_hash": snap.chain_hash,
        "created_at": snap.created_at.isoformat(),
    }
