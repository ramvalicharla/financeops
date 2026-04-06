from __future__ import annotations

import asyncio
import logging
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import (
    get_async_session,
    get_current_user,
    require_finance_team,
)
from financeops.db.models.users import IamUser
from financeops.modules.closing_checklist.service import run_auto_complete_for_event
from financeops.services.reconciliation_service import (
    create_gl_entry,
    create_tb_row,
    list_gl_entries,
    list_recon_items,
    list_tb_rows,
    run_gl_tb_reconciliation,
)
from financeops.platform.services.rbac.permission_engine import require_permission

log = logging.getLogger(__name__)
router = APIRouter()

recon_execute_guard = require_permission("recon.execute")
recon_view_guard = require_permission("recon.view")


# ── Schemas ────────────────────────────────────────────────────────────────

class GlEntryRequest(BaseModel):
    period_year: int
    period_month: int
    entity_name: str
    account_code: str
    account_name: str
    debit_amount: Decimal
    credit_amount: Decimal
    description: str | None = None
    source_ref: str | None = None
    currency: str = "USD"


class TbRowRequest(BaseModel):
    period_year: int
    period_month: int
    entity_name: str
    account_code: str
    account_name: str
    opening_balance: Decimal
    period_debit: Decimal
    period_credit: Decimal
    closing_balance: Decimal
    currency: str = "USD"


class RunReconRequest(BaseModel):
    period_year: int
    period_month: int
    entity_name: str


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.post("/gl-entries", status_code=status.HTTP_201_CREATED)
async def import_gl_entry(
    body: GlEntryRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict:
    """Import a single GL entry (INSERT ONLY)."""
    entry = await create_gl_entry(
        session,
        tenant_id=user.tenant_id,
        period_year=body.period_year,
        period_month=body.period_month,
        entity_name=body.entity_name,
        account_code=body.account_code,
        account_name=body.account_name,
        debit_amount=body.debit_amount,
        credit_amount=body.credit_amount,
        description=body.description,
        source_ref=body.source_ref,
        currency=body.currency,
        uploaded_by=user.id,
    )
    await session.flush()
    return {
        "entry_id": str(entry.id),
        "account_code": entry.account_code,
        "debit_amount": str(entry.debit_amount),
        "credit_amount": str(entry.credit_amount),
        "created_at": entry.created_at.isoformat(),
    }


@router.get("/gl-entries")
async def list_gl_entries_endpoint(
    period_year: int | None = None,
    period_month: int | None = None,
    entity_name: str | None = None,
    limit: int = 200,
    offset: int = 0,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    """List GL entries for the current tenant."""
    entries = await list_gl_entries(
        session,
        tenant_id=user.tenant_id,
        period_year=period_year,
        period_month=period_month,
        entity_name=entity_name,
        limit=limit,
        offset=offset,
    )
    return {
        "entries": [
            {
                "entry_id": str(e.id),
                "account_code": e.account_code,
                "account_name": e.account_name,
                "period": f"{e.period_year}-{e.period_month:02d}",
                "entity_name": e.entity_name,
                "debit_amount": str(e.debit_amount),
                "credit_amount": str(e.credit_amount),
                "currency": e.currency,
            }
            for e in entries
        ],
        "count": len(entries),
    }


@router.post("/tb-rows", status_code=status.HTTP_201_CREATED)
async def import_tb_row(
    body: TbRowRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_team),
) -> dict:
    """Import a single Trial Balance row (INSERT ONLY)."""
    row = await create_tb_row(
        session,
        tenant_id=user.tenant_id,
        period_year=body.period_year,
        period_month=body.period_month,
        entity_name=body.entity_name,
        account_code=body.account_code,
        account_name=body.account_name,
        opening_balance=body.opening_balance,
        period_debit=body.period_debit,
        period_credit=body.period_credit,
        closing_balance=body.closing_balance,
        currency=body.currency,
        uploaded_by=user.id,
    )
    await session.flush()
    return {
        "row_id": str(row.id),
        "account_code": row.account_code,
        "closing_balance": str(row.closing_balance),
        "created_at": row.created_at.isoformat(),
    }


@router.get("/tb-rows")
async def list_tb_rows_endpoint(
    period_year: int | None = None,
    period_month: int | None = None,
    entity_name: str | None = None,
    limit: int = 200,
    offset: int = 0,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    """List Trial Balance rows."""
    rows = await list_tb_rows(
        session,
        tenant_id=user.tenant_id,
        period_year=period_year,
        period_month=period_month,
        entity_name=entity_name,
        limit=limit,
        offset=offset,
    )
    return {
        "rows": [
            {
                "row_id": str(r.id),
                "account_code": r.account_code,
                "account_name": r.account_name,
                "period": f"{r.period_year}-{r.period_month:02d}",
                "entity_name": r.entity_name,
                "opening_balance": str(r.opening_balance),
                "closing_balance": str(r.closing_balance),
                "currency": r.currency,
            }
            for r in rows
        ],
        "count": len(rows),
    }


@router.post("/run", status_code=status.HTTP_201_CREATED)
async def run_reconciliation(
    body: RunReconRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(recon_execute_guard),
) -> dict:
    """
    Run GL/TB reconciliation for the given period and entity.
    Creates ReconItem records for every account with a non-zero difference.
    """
    items = await run_gl_tb_reconciliation(
        session,
        tenant_id=user.tenant_id,
        period_year=body.period_year,
        period_month=body.period_month,
        entity_name=body.entity_name,
        run_by=user.id,
    )
    await session.flush()
    asyncio.create_task(
        run_auto_complete_for_event(
            tenant_id=user.tenant_id,
            period=f"{body.period_year:04d}-{body.period_month:02d}",
            event="recon_complete",
        )
    )
    return {
        "period": f"{body.period_year}-{body.period_month:02d}",
        "entity_name": body.entity_name,
        "breaks_found": len(items),
        "items": [
            {
                "item_id": str(i.id),
                "account_code": i.account_code,
                "account_name": i.account_name,
                "gl_total": str(i.gl_total),
                "tb_closing_balance": str(i.tb_closing_balance),
                "difference": str(i.difference),
                "status": i.status,
            }
            for i in items
        ],
    }


@router.get("/items")
async def list_reconciliation_items(
    period_year: int | None = None,
    period_month: int | None = None,
    entity_name: str | None = None,
    item_status: str | None = None,
    limit: int = 100,
    offset: int = 0,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(recon_view_guard),
) -> dict:
    """List reconciliation break items."""
    items = await list_recon_items(
        session,
        tenant_id=user.tenant_id,
        period_year=period_year,
        period_month=period_month,
        entity_name=entity_name,
        status=item_status,
        limit=limit,
        offset=offset,
    )
    return {
        "items": [
            {
                "item_id": str(i.id),
                "account_code": i.account_code,
                "account_name": i.account_name,
                "period": f"{i.period_year}-{i.period_month:02d}",
                "entity_name": i.entity_name,
                "gl_total": str(i.gl_total),
                "tb_closing_balance": str(i.tb_closing_balance),
                "difference": str(i.difference),
                "status": i.status,
                "recon_type": i.recon_type,
            }
            for i in items
        ],
        "count": len(items),
    }
