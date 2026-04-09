from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user
from financeops.core.intent.api import build_idempotency_key, build_intent_actor
from financeops.core.intent.enums import IntentType
from financeops.core.intent.service import IntentService
from financeops.db.models.users import IamUser
from financeops.modules.working_capital.models import APLineItem, ARLineItem, WCSnapshot
from financeops.modules.working_capital.service import get_wc_dashboard
from financeops.platform.services.tenancy.entity_access import assert_entity_access
from financeops.shared_kernel.pagination import Paginated

router = APIRouter(prefix="/working-capital", tags=["working-capital"])


def _current_period() -> str:
    return datetime.now(UTC).strftime("%Y-%m")


async def _ensure_snapshot(
    request: Request,
    session: AsyncSession,
    *,
    user: IamUser,
    period: str,
    entity_id: uuid.UUID | None,
) -> WCSnapshot:
    existing = (
        await session.execute(
            select(WCSnapshot)
            .where(
                WCSnapshot.tenant_id == user.tenant_id,
                WCSnapshot.period == period,
                WCSnapshot.entity_id == entity_id,
            )
            .order_by(WCSnapshot.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    result = await IntentService(session).submit_intent(
        intent_type=IntentType.COMPUTE_WORKING_CAPITAL_SNAPSHOT,
        actor=build_intent_actor(request, user),
        payload={
            "period": period,
            "entity_id": str(entity_id) if entity_id else None,
        },
        idempotency_key=build_idempotency_key(
            request,
            intent_type=IntentType.COMPUTE_WORKING_CAPITAL_SNAPSHOT,
            actor=user,
            body={"period": period, "entity_id": str(entity_id) if entity_id else None},
        ),
    )
    snapshot_id = uuid.UUID(str((result.record_refs or {})["snapshot_id"]))
    return (
        await session.execute(
            select(WCSnapshot).where(
                WCSnapshot.id == snapshot_id,
                WCSnapshot.tenant_id == user.tenant_id,
            )
        )
    ).scalar_one()


@router.get("/dashboard")
async def wc_dashboard(
    request: Request,
    period: str | None = Query(default=None),
    entity_id: uuid.UUID | None = Query(default=None),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    target_period = period or _current_period()
    await assert_entity_access(
        session=session,
        tenant_id=user.tenant_id,
        entity_id=entity_id,
        user_id=user.id,
        user_role=user.role,
    )
    await _ensure_snapshot(
        request,
        session,
        user=user,
        period=target_period,
        entity_id=entity_id,
    )
    return await get_wc_dashboard(session, user.tenant_id, period=target_period)


@router.get("/ar")
async def list_ar(
    request: Request,
    period: str | None = Query(default=None),
    aging_bucket: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> Paginated[dict]:
    target_period = period or _current_period()
    snapshot = (
        await session.execute(
            select(WCSnapshot)
            .where(
                WCSnapshot.tenant_id == user.tenant_id,
                WCSnapshot.period == target_period,
            )
            .order_by(WCSnapshot.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if snapshot is None:
        snapshot = await _ensure_snapshot(
            request,
            session,
            user=user,
            period=target_period,
            entity_id=None,
        )

    stmt = select(ARLineItem).where(
        ARLineItem.tenant_id == user.tenant_id,
        ARLineItem.snapshot_id == snapshot.id,
    )
    if aging_bucket:
        stmt = stmt.where(ARLineItem.aging_bucket == aging_bucket)

    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (
        await session.execute(
            stmt.order_by(ARLineItem.days_overdue.desc(), ARLineItem.amount.desc())
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()
    return Paginated[dict](
        data=[
            {
                "id": str(row.id),
                "customer_name": row.customer_name,
                "amount": row.amount,
                "days_overdue": row.days_overdue,
                "aging_bucket": row.aging_bucket,
                "payment_probability_score": row.payment_probability_score,
            }
            for row in rows
        ],
        total=int(total),
        limit=limit,
        offset=offset,
    )


@router.get("/ap")
async def list_ap(
    request: Request,
    period: str | None = Query(default=None),
    aging_bucket: str | None = Query(default=None),
    discount_only: bool = Query(default=False),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> Paginated[dict]:
    target_period = period or _current_period()
    snapshot = (
        await session.execute(
            select(WCSnapshot)
            .where(
                WCSnapshot.tenant_id == user.tenant_id,
                WCSnapshot.period == target_period,
            )
            .order_by(WCSnapshot.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if snapshot is None:
        snapshot = await _ensure_snapshot(
            request,
            session,
            user=user,
            period=target_period,
            entity_id=None,
        )

    stmt = select(APLineItem).where(
        APLineItem.tenant_id == user.tenant_id,
        APLineItem.snapshot_id == snapshot.id,
    )
    if aging_bucket:
        stmt = stmt.where(APLineItem.aging_bucket == aging_bucket)
    if discount_only:
        stmt = stmt.where(APLineItem.early_payment_discount_available.is_(True))

    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (
        await session.execute(
            stmt.order_by(APLineItem.days_overdue.desc(), APLineItem.amount.desc())
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()
    return Paginated[dict](
        data=[
            {
                "id": str(row.id),
                "vendor_name": row.vendor_name,
                "amount": row.amount,
                "days_overdue": row.days_overdue,
                "aging_bucket": row.aging_bucket,
                "early_payment_discount_available": row.early_payment_discount_available,
                "early_payment_discount_pct": row.early_payment_discount_pct,
            }
            for row in rows
        ],
        total=int(total),
        limit=limit,
        offset=offset,
    )


@router.get("/trends")
async def trends(
    periods_history: int = Query(default=12, ge=1, le=24),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    rows = (
        await session.execute(
            select(WCSnapshot)
            .where(WCSnapshot.tenant_id == user.tenant_id)
            .order_by(WCSnapshot.period.desc(), WCSnapshot.created_at.desc())
            .limit(periods_history)
        )
    ).scalars().all()
    return [
        {
            "period": row.period,
            "dso_days": row.dso_days,
            "dpo_days": row.dpo_days,
            "ccc_days": row.ccc_days,
            "net_working_capital": row.net_working_capital,
        }
        for row in rows
    ]

