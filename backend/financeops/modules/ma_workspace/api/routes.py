from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user, require_finance_leader
from financeops.core.exceptions import InsufficientCreditsError, NotFoundError, ValidationError
from financeops.db.models.users import IamUser, UserRole
from financeops.modules.ma_workspace.models import MADDItem, MADocument, MAValuation, MAWorkspace, MAWorkspaceMember
from financeops.modules.ma_workspace.service import (
    add_workspace_member,
    compute_comparable_companies_valuation,
    compute_dcf_valuation,
    create_dd_item,
    create_workspace,
    get_dd_tracker,
    list_workspace_documents,
    register_document,
    update_dd_item,
    update_workspace,
)
from financeops.shared_kernel.pagination import Paginated

router = APIRouter(prefix="/advisory/ma", tags=["advisory-ma"])


class CreateWorkspaceRequest(BaseModel):
    workspace_name: str
    deal_codename: str
    deal_type: str
    target_company_name: str
    indicative_deal_value: str | None = None


class PatchWorkspaceRequest(BaseModel):
    deal_status: str | None = None
    indicative_deal_value: str | None = None


class AddMemberRequest(BaseModel):
    user_id: uuid.UUID
    member_role: str


class CreateValuationRequest(BaseModel):
    valuation_name: str
    valuation_method: str
    assumptions: dict[str, str] = Field(default_factory=dict)


class CreateDDItemRequest(BaseModel):
    category: str
    item_name: str
    description: str | None = None
    priority: str = "medium"
    assigned_to: uuid.UUID | None = None
    due_date: date | None = None


class PatchDDItemRequest(BaseModel):
    status: str | None = None
    response_notes: str | None = None


class RegisterDocumentRequest(BaseModel):
    document_name: str
    document_type: str
    file_url: str | None = None
    file_size_bytes: int | None = None
    is_confidential: bool = True


def _to_decimal(value: str, field_name: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"{field_name} must be a decimal string") from exc


def _serialize_workspace(row: MAWorkspace) -> dict:
    return {
        "id": str(row.id),
        "tenant_id": str(row.tenant_id),
        "workspace_name": row.workspace_name,
        "deal_codename": row.deal_codename,
        "deal_type": row.deal_type,
        "target_company_name": row.target_company_name,
        "deal_status": row.deal_status,
        "indicative_deal_value": format(Decimal(str(row.indicative_deal_value)), "f") if row.indicative_deal_value is not None else None,
        "deal_value_currency": row.deal_value_currency,
        "credit_cost_monthly": row.credit_cost_monthly,
        "credit_charged_at": row.credit_charged_at.isoformat() if row.credit_charged_at else None,
        "created_by": str(row.created_by),
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


def _serialize_member(row: MAWorkspaceMember) -> dict:
    return {
        "id": str(row.id),
        "workspace_id": str(row.workspace_id),
        "tenant_id": str(row.tenant_id),
        "user_id": str(row.user_id),
        "member_role": row.member_role,
        "added_at": row.added_at.isoformat(),
        "removed_at": row.removed_at.isoformat() if row.removed_at else None,
    }


def _serialize_valuation(row: MAValuation) -> dict:
    return {
        "id": str(row.id),
        "workspace_id": str(row.workspace_id),
        "tenant_id": str(row.tenant_id),
        "valuation_name": row.valuation_name,
        "valuation_method": row.valuation_method,
        "assumptions": row.assumptions,
        "enterprise_value": format(Decimal(str(row.enterprise_value)), "f"),
        "equity_value": format(Decimal(str(row.equity_value)), "f"),
        "net_debt_used": format(Decimal(str(row.net_debt_used)), "f"),
        "ev_ebitda_multiple": format(Decimal(str(row.ev_ebitda_multiple)), "f"),
        "ev_revenue_multiple": format(Decimal(str(row.ev_revenue_multiple)), "f"),
        "valuation_range_low": format(Decimal(str(row.valuation_range_low)), "f"),
        "valuation_range_high": format(Decimal(str(row.valuation_range_high)), "f"),
        "computed_at": row.computed_at.isoformat(),
        "computed_by": str(row.computed_by),
        "notes": row.notes,
    }


def _serialize_dd_item(row: MADDItem) -> dict:
    return {
        "id": str(row.id),
        "workspace_id": str(row.workspace_id),
        "tenant_id": str(row.tenant_id),
        "category": row.category,
        "item_name": row.item_name,
        "description": row.description,
        "status": row.status,
        "priority": row.priority,
        "assigned_to": str(row.assigned_to) if row.assigned_to else None,
        "due_date": row.due_date.isoformat() if row.due_date else None,
        "response_notes": row.response_notes,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


def _serialize_document(row: MADocument) -> dict:
    return {
        "id": str(row.id),
        "workspace_id": str(row.workspace_id),
        "tenant_id": str(row.tenant_id),
        "document_name": row.document_name,
        "document_type": row.document_type,
        "version": row.version,
        "file_url": row.file_url,
        "file_size_bytes": row.file_size_bytes,
        "uploaded_by": str(row.uploaded_by),
        "is_confidential": row.is_confidential,
        "created_at": row.created_at.isoformat(),
    }


async def _ensure_lead_or_finance(session: AsyncSession, user: IamUser, workspace_id: uuid.UUID) -> None:
    if user.role in {UserRole.super_admin, UserRole.finance_leader}:
        return
    role = (
        await session.execute(
            select(MAWorkspaceMember.member_role).where(
                MAWorkspaceMember.tenant_id == user.tenant_id,
                MAWorkspaceMember.workspace_id == workspace_id,
                MAWorkspaceMember.user_id == user.id,
                MAWorkspaceMember.removed_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if role != "lead_advisor":
        raise HTTPException(status_code=403, detail="lead_advisor or finance_leader required")


@router.post("/workspaces", status_code=status.HTTP_201_CREATED)
async def create_workspace_endpoint(
    body: CreateWorkspaceRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> dict:
    try:
        workspace = await create_workspace(
            session,
            tenant_id=user.tenant_id,
            workspace_name=body.workspace_name,
            deal_codename=body.deal_codename,
            deal_type=body.deal_type,
            target_company_name=body.target_company_name,
            created_by=user.id,
            indicative_deal_value=_to_decimal(body.indicative_deal_value, "indicative_deal_value") if body.indicative_deal_value else None,
        )
    except InsufficientCreditsError as exc:
        raise HTTPException(status_code=402, detail=exc.message) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc
    await session.flush()
    return _serialize_workspace(workspace)


@router.get("/workspaces")
async def list_workspaces_endpoint(
    deal_status: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> Paginated[dict]:
    stmt = select(MAWorkspace).where(MAWorkspace.tenant_id == user.tenant_id)
    if deal_status:
        stmt = stmt.where(MAWorkspace.deal_status == deal_status)
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (
        await session.execute(
            stmt.order_by(MAWorkspace.created_at.desc(), MAWorkspace.id.desc()).limit(limit).offset(offset)
        )
    ).scalars().all()
    return Paginated[dict](
        data=[_serialize_workspace(row) for row in rows],
        total=int(total),
        limit=limit,
        offset=offset,
    )


@router.get("/workspaces/{workspace_id}")
async def get_workspace_endpoint(
    workspace_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> dict:
    workspace = (
        await session.execute(
            select(MAWorkspace).where(
                MAWorkspace.id == workspace_id,
                MAWorkspace.tenant_id == user.tenant_id,
            )
        )
    ).scalar_one_or_none()
    if workspace is None:
        raise HTTPException(status_code=404, detail="M&A workspace not found")

    members = (
        await session.execute(
            select(MAWorkspaceMember).where(
                MAWorkspaceMember.tenant_id == user.tenant_id,
                MAWorkspaceMember.workspace_id == workspace_id,
            )
        )
    ).scalars().all()
    summary = await get_dd_tracker(session, workspace_id=workspace_id, tenant_id=user.tenant_id)
    return {
        "workspace": _serialize_workspace(workspace),
        "members": [_serialize_member(row) for row in members],
        "dd_summary": {
            "total_items": summary["total_items"],
            "by_status": summary["by_status"],
            "by_category": summary["by_category"],
            "by_priority": summary["by_priority"],
            "completion_pct": format(Decimal(str(summary["completion_pct"])), "f"),
            "flagged_items": [_serialize_dd_item(item) for item in summary["flagged_items"]],
            "overdue_items": [_serialize_dd_item(item) for item in summary["overdue_items"]],
        },
    }


@router.patch("/workspaces/{workspace_id}")
async def patch_workspace_endpoint(
    workspace_id: uuid.UUID,
    body: PatchWorkspaceRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    await _ensure_lead_or_finance(session, user, workspace_id)
    try:
        row = await update_workspace(
            session,
            workspace_id=workspace_id,
            tenant_id=user.tenant_id,
            deal_status=body.deal_status,
            indicative_deal_value=(
                _to_decimal(body.indicative_deal_value, "indicative_deal_value")
                if body.indicative_deal_value is not None
                else None
            ),
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
    await session.flush()
    return _serialize_workspace(row)


@router.post("/workspaces/{workspace_id}/members", status_code=status.HTTP_201_CREATED)
async def add_member_endpoint(
    workspace_id: uuid.UUID,
    body: AddMemberRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> dict:
    try:
        row = await add_workspace_member(
            session,
            workspace_id=workspace_id,
            tenant_id=user.tenant_id,
            user_id=body.user_id,
            member_role=body.member_role,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
    await session.flush()
    return _serialize_member(row)


@router.get("/workspaces/{workspace_id}/valuations")
async def list_valuations_endpoint(
    workspace_id: uuid.UUID,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> Paginated[dict]:
    stmt = select(MAValuation).where(
        MAValuation.tenant_id == user.tenant_id,
        MAValuation.workspace_id == workspace_id,
    )
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (
        await session.execute(
            stmt.order_by(MAValuation.computed_at.desc(), MAValuation.id.desc()).limit(limit).offset(offset)
        )
    ).scalars().all()
    return Paginated[dict](
        data=[_serialize_valuation(row) for row in rows],
        total=int(total),
        limit=limit,
        offset=offset,
    )


@router.post("/workspaces/{workspace_id}/valuations", status_code=status.HTTP_201_CREATED)
async def create_valuation_endpoint(
    workspace_id: uuid.UUID,
    body: CreateValuationRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> dict:
    method = body.valuation_method
    try:
        if method == "dcf":
            row = await compute_dcf_valuation(
                session,
                workspace_id=workspace_id,
                tenant_id=user.tenant_id,
                computed_by=user.id,
                valuation_name=body.valuation_name,
                assumptions=body.assumptions,
            )
        elif method == "comparable_companies":
            row = await compute_comparable_companies_valuation(
                session,
                workspace_id=workspace_id,
                tenant_id=user.tenant_id,
                computed_by=user.id,
                valuation_name=body.valuation_name,
                assumptions=body.assumptions,
            )
        else:
            raise HTTPException(status_code=422, detail="Unsupported valuation_method")
    except (NotFoundError, ValidationError) as exc:
        message = exc.message if hasattr(exc, "message") else str(exc)
        raise HTTPException(status_code=422, detail=message) from exc

    await session.flush()
    return _serialize_valuation(row)


@router.get("/workspaces/{workspace_id}/dd")
async def dd_summary_endpoint(
    workspace_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> dict:
    summary = await get_dd_tracker(session, workspace_id=workspace_id, tenant_id=user.tenant_id)
    rows = (
        await session.execute(
            select(MADDItem)
            .where(
                MADDItem.tenant_id == user.tenant_id,
                MADDItem.workspace_id == workspace_id,
            )
            .order_by(MADDItem.category.asc(), MADDItem.created_at.asc())
        )
    ).scalars().all()
    return {
        "summary": {
            "total_items": summary["total_items"],
            "by_status": summary["by_status"],
            "by_category": summary["by_category"],
            "by_priority": summary["by_priority"],
            "completion_pct": format(Decimal(str(summary["completion_pct"])), "f"),
            "flagged_items": [_serialize_dd_item(item) for item in summary["flagged_items"]],
            "overdue_items": [_serialize_dd_item(item) for item in summary["overdue_items"]],
        },
        "items": [_serialize_dd_item(item) for item in rows],
    }


@router.post("/workspaces/{workspace_id}/dd", status_code=status.HTTP_201_CREATED)
async def create_dd_item_endpoint(
    workspace_id: uuid.UUID,
    body: CreateDDItemRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> dict:
    try:
        row = await create_dd_item(
            session,
            workspace_id=workspace_id,
            tenant_id=user.tenant_id,
            category=body.category,
            item_name=body.item_name,
            description=body.description,
            priority=body.priority,
            assigned_to=body.assigned_to,
            due_date=body.due_date,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
    await session.flush()
    return _serialize_dd_item(row)


@router.patch("/workspaces/{workspace_id}/dd/{item_id}")
async def patch_dd_item_endpoint(
    workspace_id: uuid.UUID,
    item_id: uuid.UUID,
    body: PatchDDItemRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> dict:
    try:
        row = await update_dd_item(
            session,
            workspace_id=workspace_id,
            item_id=item_id,
            tenant_id=user.tenant_id,
            status=body.status,
            response_notes=body.response_notes,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
    await session.flush()
    return _serialize_dd_item(row)


@router.get("/workspaces/{workspace_id}/documents")
async def list_documents_endpoint(
    workspace_id: uuid.UUID,
    document_type: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> Paginated[dict]:
    rows, total = await list_workspace_documents(
        session,
        workspace_id=workspace_id,
        tenant_id=user.tenant_id,
        document_type=document_type,
        limit=limit,
        offset=offset,
    )
    return Paginated[dict](
        data=[_serialize_document(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/workspaces/{workspace_id}/documents", status_code=status.HTTP_201_CREATED)
async def register_document_endpoint(
    workspace_id: uuid.UUID,
    body: RegisterDocumentRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> dict:
    row = await register_document(
        session,
        workspace_id=workspace_id,
        tenant_id=user.tenant_id,
        document_name=body.document_name,
        document_type=body.document_type,
        file_url=body.file_url,
        file_size_bytes=body.file_size_bytes,
        is_confidential=body.is_confidential,
        uploaded_by=user.id,
    )
    await session.flush()
    return _serialize_document(row)


__all__ = ["router"]
