from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import InsufficientCreditsError, NotFoundError, ValidationError
from financeops.db.models.credits import CreditReservation, ReservationStatus
from financeops.modules.ma_workspace.models import MADDItem, MADocument, MAValuation, MAWorkspace, MAWorkspaceMember
from financeops.services.credit_service import confirm_credits, reserve_credits


def _q2(value: Decimal) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _q4(value: Decimal) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.0000"), rounding=ROUND_HALF_UP)


def _to_decimal(value: Any, default: str = "0") -> Decimal:
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal(default)


def _jsonify(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, list):
        return [_jsonify(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _jsonify(v) for k, v in value.items()}
    return value


async def _load_workspace(session: AsyncSession, *, tenant_id: uuid.UUID, workspace_id: uuid.UUID) -> MAWorkspace:
    row = (
        await session.execute(
            select(MAWorkspace).where(
                MAWorkspace.id == workspace_id,
                MAWorkspace.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError("M&A workspace not found")
    return row


async def _pending_workspace_reservation(session: AsyncSession, *, tenant_id: uuid.UUID, workspace_id: uuid.UUID) -> uuid.UUID | None:
    return (
        await session.execute(
            select(CreditReservation.id).where(
                CreditReservation.tenant_id == tenant_id,
                CreditReservation.task_type == f"ma:{workspace_id}:monthly",
                CreditReservation.status == ReservationStatus.pending,
            )
        )
    ).scalar_one_or_none()


async def create_workspace(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    workspace_name: str,
    deal_codename: str,
    deal_type: str,
    target_company_name: str,
    created_by: uuid.UUID,
    indicative_deal_value: Decimal | None = None,
) -> MAWorkspace:
    """
    Create M&A workspace and charge monthly advisory credits.
    """
    if deal_type not in {"acquisition", "merger", "divestiture", "minority_investment", "joint_venture"}:
        raise ValidationError("invalid deal_type")

    workspace = MAWorkspace(
        tenant_id=tenant_id,
        workspace_name=workspace_name,
        deal_codename=deal_codename,
        deal_type=deal_type,
        target_company_name=target_company_name,
        deal_status="active",
        indicative_deal_value=_q2(indicative_deal_value) if indicative_deal_value is not None else None,
        credit_cost_monthly=1000,
        created_by=created_by,
    )
    session.add(workspace)
    await session.flush()

    reservation_id = await reserve_credits(
        session,
        tenant_id=tenant_id,
        task_type=f"ma:{workspace.id}:monthly",
        amount=Decimal("1000"),
    )
    if reservation_id is None:
        raise InsufficientCreditsError("Unable to reserve M&A workspace credits")

    await confirm_credits(
        session,
        tenant_id=tenant_id,
        reservation_id=reservation_id,
        user_id=created_by,
    )
    workspace.credit_charged_at = datetime.now(UTC)

    session.add(
        MAWorkspaceMember(
            workspace_id=workspace.id,
            tenant_id=tenant_id,
            user_id=created_by,
            member_role="lead_advisor",
        )
    )
    await session.flush()

    await seed_dd_checklist(
        session,
        workspace_id=workspace.id,
        tenant_id=tenant_id,
        deal_type=deal_type,
    )
    await session.flush()
    return workspace


async def _current_dd_member_role(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
) -> str | None:
    row = (
        await session.execute(
            select(MAWorkspaceMember.member_role).where(
                MAWorkspaceMember.tenant_id == tenant_id,
                MAWorkspaceMember.workspace_id == workspace_id,
                MAWorkspaceMember.user_id == user_id,
                MAWorkspaceMember.removed_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    return row


async def compute_dcf_valuation(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    tenant_id: uuid.UUID,
    computed_by: uuid.UUID,
    valuation_name: str,
    assumptions: dict,
) -> MAValuation:
    """
    Compute DCF valuation snapshot using Decimal arithmetic.
    """
    await _load_workspace(session, tenant_id=tenant_id, workspace_id=workspace_id)

    ebitda_base = _to_decimal(assumptions.get("ebitda_base", "1000000"))
    revenue_base = _to_decimal(assumptions.get("revenue_base", ebitda_base * Decimal("4")))
    terminal_growth_rate = _to_decimal(assumptions.get("terminal_growth_rate", "0.03"))
    discount_rate = _to_decimal(assumptions.get("discount_rate", "0.12"))
    tax_rate = _to_decimal(assumptions.get("tax_rate", "0.25"))
    capex_pct = _to_decimal(assumptions.get("capex_pct_revenue", "0.04"))
    nwc_pct = _to_decimal(assumptions.get("nwc_change_pct_revenue", "0.02"))
    net_debt = _to_decimal(assumptions.get("net_debt", "0"))

    if discount_rate <= terminal_growth_rate:
        raise ValidationError("discount_rate must be greater than terminal_growth_rate")

    pv_fcff_total = Decimal("0")
    revenue_prev = revenue_base
    fcff_year_5 = Decimal("0")

    for year in range(1, 6):
        growth = _to_decimal(assumptions.get(f"revenue_growth_year_{year}", "0.05"))
        margin = _to_decimal(assumptions.get(f"ebitda_margin_year_{year}", "0.20"))
        revenue = _q2(revenue_prev * (Decimal("1") + growth))
        ebitda = _q2(revenue * margin)
        depreciation = _q2(revenue * Decimal("0.03"))
        ebit = _q2(ebitda - depreciation)
        nopat = _q2(ebit * (Decimal("1") - tax_rate))
        capex = _q2(revenue * capex_pct)
        delta_nwc = _q2(revenue * nwc_pct)
        fcff = _q2(nopat + depreciation - capex - delta_nwc)
        pv_fcff = _q2(fcff / ((Decimal("1") + discount_rate) ** Decimal(str(year))))
        pv_fcff_total += pv_fcff

        revenue_prev = revenue
        fcff_year_5 = fcff

    terminal_value = _q2(
        fcff_year_5 * (Decimal("1") + terminal_growth_rate) / (discount_rate - terminal_growth_rate)
    )
    pv_terminal = _q2(terminal_value / ((Decimal("1") + discount_rate) ** Decimal("5")))

    enterprise_value = _q2(pv_fcff_total + pv_terminal)
    equity_value = _q2(enterprise_value - net_debt)

    ev_ebitda = Decimal("0") if ebitda_base == Decimal("0") else _q4(enterprise_value / ebitda_base)
    ev_revenue = Decimal("0") if revenue_base == Decimal("0") else _q4(enterprise_value / revenue_base)

    valuation = MAValuation(
        workspace_id=workspace_id,
        tenant_id=tenant_id,
        valuation_name=valuation_name,
        valuation_method="dcf",
        assumptions=_jsonify(assumptions),
        enterprise_value=enterprise_value,
        equity_value=equity_value,
        net_debt_used=_q2(net_debt),
        ev_ebitda_multiple=ev_ebitda,
        ev_revenue_multiple=ev_revenue,
        valuation_range_low=_q2(enterprise_value * Decimal("0.90")),
        valuation_range_high=_q2(enterprise_value * Decimal("1.10")),
        computed_by=computed_by,
    )
    session.add(valuation)
    await session.flush()
    return valuation


async def compute_comparable_companies_valuation(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    tenant_id: uuid.UUID,
    computed_by: uuid.UUID,
    valuation_name: str,
    assumptions: dict,
) -> MAValuation:
    """
    Compute blended comparable-companies valuation.
    """
    await _load_workspace(session, tenant_id=tenant_id, workspace_id=workspace_id)

    ltm_ebitda = _to_decimal(assumptions.get("ltm_ebitda", "0"))
    ltm_revenue = _to_decimal(assumptions.get("ltm_revenue", "0"))
    peer_ev_ebitda = _to_decimal(assumptions.get("peer_ev_ebitda_median", "0"))
    peer_ev_revenue = _to_decimal(assumptions.get("peer_ev_revenue_median", "0"))
    control_premium = _to_decimal(assumptions.get("control_premium_pct", "0"))
    net_debt = _to_decimal(assumptions.get("net_debt", "0"))

    ev_from_ebitda = _q2(ltm_ebitda * peer_ev_ebitda)
    ev_from_revenue = _q2(ltm_revenue * peer_ev_revenue)
    blended_ev = _q2((ev_from_ebitda + ev_from_revenue) / Decimal("2"))
    enterprise_value = _q2(blended_ev * (Decimal("1") + control_premium))
    equity_value = _q2(enterprise_value - net_debt)

    valuation = MAValuation(
        workspace_id=workspace_id,
        tenant_id=tenant_id,
        valuation_name=valuation_name,
        valuation_method="comparable_companies",
        assumptions=_jsonify(assumptions),
        enterprise_value=enterprise_value,
        equity_value=equity_value,
        net_debt_used=_q2(net_debt),
        ev_ebitda_multiple=_q4(peer_ev_ebitda),
        ev_revenue_multiple=_q4(peer_ev_revenue),
        valuation_range_low=_q2(enterprise_value * Decimal("0.90")),
        valuation_range_high=_q2(enterprise_value * Decimal("1.10")),
        computed_by=computed_by,
    )
    session.add(valuation)
    await session.flush()
    return valuation


async def get_dd_tracker(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> dict:
    """
    Return DD tracker summary and item groupings.
    """
    await _load_workspace(session, tenant_id=tenant_id, workspace_id=workspace_id)
    items = (
        await session.execute(
            select(MADDItem)
            .where(
                MADDItem.tenant_id == tenant_id,
                MADDItem.workspace_id == workspace_id,
            )
            .order_by(MADDItem.created_at.asc(), MADDItem.id.asc())
        )
    ).scalars().all()

    total_items = len(items)
    by_status: dict[str, int] = {}
    by_category: dict[str, int] = {}
    by_priority: dict[str, int] = {}
    completed = 0

    today = datetime.now(UTC).date()
    flagged_items: list[MADDItem] = []
    overdue_items: list[MADDItem] = []
    for item in items:
        by_status[item.status] = by_status.get(item.status, 0) + 1
        by_category[item.category] = by_category.get(item.category, 0) + 1
        by_priority[item.priority] = by_priority.get(item.priority, 0) + 1
        if item.status == "completed":
            completed += 1
        if item.status == "flagged":
            flagged_items.append(item)
        if item.due_date is not None and item.due_date < today and item.status not in {"completed", "waived"}:
            overdue_items.append(item)

    completion_pct = Decimal("0.00")
    if total_items > 0:
        completion_pct = _q2((Decimal(str(completed)) / Decimal(str(total_items))) * Decimal("100"))

    return {
        "total_items": total_items,
        "by_status": by_status,
        "by_category": by_category,
        "by_priority": by_priority,
        "completion_pct": completion_pct,
        "flagged_items": flagged_items,
        "overdue_items": overdue_items,
    }


async def seed_dd_checklist(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    tenant_id: uuid.UUID,
    deal_type: str,
) -> list[MADDItem]:
    """
    Seed DD checklist baseline items.
    """
    del deal_type
    existing = (
        await session.execute(
            select(MADDItem.id).where(
                MADDItem.tenant_id == tenant_id,
                MADDItem.workspace_id == workspace_id,
            )
        )
    ).scalars().all()
    if existing:
        rows = (
            await session.execute(
                select(MADDItem).where(
                    MADDItem.tenant_id == tenant_id,
                    MADDItem.workspace_id == workspace_id,
                )
            )
        ).scalars().all()
        return rows

    templates = [
        ("financial", "3 years audited financials"),
        ("financial", "Management accounts (last 24 months)"),
        ("financial", "Budget vs actual analysis"),
        ("financial", "Working capital analysis"),
        ("financial", "Debt schedule"),
        ("financial", "Cap table"),
        ("legal", "Corporate structure chart"),
        ("legal", "Material contracts"),
        ("legal", "IP ownership schedule"),
        ("legal", "Litigation schedule"),
        ("tax", "Tax returns (3 years)"),
        ("tax", "Transfer pricing documentation"),
        ("tax", "Tax positions memo"),
        ("commercial", "Customer contracts"),
        ("commercial", "Supplier agreements"),
        ("commercial", "Market analysis"),
    ]

    rows: list[MADDItem] = []
    for category, item_name in templates:
        row = MADDItem(
            workspace_id=workspace_id,
            tenant_id=tenant_id,
            category=category,
            item_name=item_name,
            status="open",
            priority="medium",
        )
        session.add(row)
        rows.append(row)
    await session.flush()
    return rows


async def add_workspace_member(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    member_role: str,
) -> MAWorkspaceMember:
    await _load_workspace(session, tenant_id=tenant_id, workspace_id=workspace_id)
    existing = (
        await session.execute(
            select(MAWorkspaceMember).where(
                MAWorkspaceMember.tenant_id == tenant_id,
                MAWorkspaceMember.workspace_id == workspace_id,
                MAWorkspaceMember.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        existing.member_role = member_role
        existing.removed_at = None
        await session.flush()
        return existing

    row = MAWorkspaceMember(
        workspace_id=workspace_id,
        tenant_id=tenant_id,
        user_id=user_id,
        member_role=member_role,
    )
    session.add(row)
    await session.flush()
    return row


async def update_workspace(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    tenant_id: uuid.UUID,
    *,
    deal_status: str | None = None,
    indicative_deal_value: Decimal | None = None,
) -> MAWorkspace:
    row = await _load_workspace(session, tenant_id=tenant_id, workspace_id=workspace_id)
    if deal_status is not None:
        row.deal_status = deal_status
    if indicative_deal_value is not None:
        row.indicative_deal_value = _q2(indicative_deal_value)
    row.updated_at = datetime.now(UTC)
    await session.flush()
    return row


async def create_dd_item(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    tenant_id: uuid.UUID,
    *,
    category: str,
    item_name: str,
    description: str | None = None,
    priority: str = "medium",
    assigned_to: uuid.UUID | None = None,
    due_date: date | None = None,
) -> MADDItem:
    await _load_workspace(session, tenant_id=tenant_id, workspace_id=workspace_id)
    row = MADDItem(
        workspace_id=workspace_id,
        tenant_id=tenant_id,
        category=category,
        item_name=item_name,
        description=description,
        priority=priority,
        assigned_to=assigned_to,
        due_date=due_date,
    )
    session.add(row)
    await session.flush()
    return row


async def update_dd_item(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    item_id: uuid.UUID,
    tenant_id: uuid.UUID,
    *,
    status: str | None = None,
    response_notes: str | None = None,
) -> MADDItem:
    await _load_workspace(session, tenant_id=tenant_id, workspace_id=workspace_id)
    row = (
        await session.execute(
            select(MADDItem).where(
                MADDItem.id == item_id,
                MADDItem.workspace_id == workspace_id,
                MADDItem.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError("DD item not found")
    if status is not None:
        row.status = status
    if response_notes is not None:
        row.response_notes = response_notes
    row.updated_at = datetime.now(UTC)
    await session.flush()
    return row


async def list_workspace_documents(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    tenant_id: uuid.UUID,
    *,
    document_type: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[MADocument], int]:
    await _load_workspace(session, tenant_id=tenant_id, workspace_id=workspace_id)
    stmt = select(MADocument).where(
        MADocument.tenant_id == tenant_id,
        MADocument.workspace_id == workspace_id,
    )
    if document_type:
        stmt = stmt.where(MADocument.document_type == document_type)

    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (
        await session.execute(
            stmt.order_by(MADocument.created_at.desc(), MADocument.id.desc()).limit(limit).offset(offset)
        )
    ).scalars().all()
    return rows, int(total)


async def register_document(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    tenant_id: uuid.UUID,
    *,
    document_name: str,
    document_type: str,
    file_url: str | None,
    file_size_bytes: int | None,
    is_confidential: bool,
    uploaded_by: uuid.UUID,
) -> MADocument:
    await _load_workspace(session, tenant_id=tenant_id, workspace_id=workspace_id)

    latest_version = (
        await session.execute(
            select(MADocument.version)
            .where(
                MADocument.tenant_id == tenant_id,
                MADocument.workspace_id == workspace_id,
                MADocument.document_name == document_name,
            )
            .order_by(MADocument.version.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    version = int(latest_version or 0) + 1

    row = MADocument(
        workspace_id=workspace_id,
        tenant_id=tenant_id,
        document_name=document_name,
        document_type=document_type,
        version=version,
        file_url=file_url,
        file_size_bytes=file_size_bytes,
        uploaded_by=uploaded_by,
        is_confidential=is_confidential,
    )
    session.add(row)
    await session.flush()
    return row


__all__ = [
    "create_workspace",
    "compute_dcf_valuation",
    "compute_comparable_companies_valuation",
    "get_dd_tracker",
    "seed_dd_checklist",
    "add_workspace_member",
    "update_workspace",
    "create_dd_item",
    "update_dd_item",
    "list_workspace_documents",
    "register_document",
]
