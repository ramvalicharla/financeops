from __future__ import annotations

from io import BytesIO
import uuid
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from openpyxl import Workbook
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user, require_finance_leader
from financeops.core.exceptions import NotFoundError, ValidationError
from financeops.db.models.users import IamUser
from financeops.modules.budgeting.models import BudgetLineItem, BudgetVersion
from financeops.modules.budgeting.service import (
    approve_budget,
    create_budget_version,
    get_budget_summary,
    get_budget_vs_actual,
    upsert_budget_line,
)
from financeops.shared_kernel.pagination import Paginated

router = APIRouter(prefix="/budget", tags=["budgeting"])


class CreateVersionRequest(BaseModel):
    fiscal_year: int
    version_name: str
    copy_from_version_id: uuid.UUID | None = None


class AddLineRequest(BaseModel):
    mis_line_item: str
    mis_category: str
    monthly_values: list[str]
    basis: str | None = None
    entity_id: uuid.UUID | None = None


def _to_decimal(value: str, field: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"{field} must be a decimal string") from exc


def _serialize_version(version: BudgetVersion, *, line_item_count: int | None = None) -> dict:
    return {
        "id": str(version.id),
        "tenant_id": str(version.tenant_id),
        "fiscal_year": version.fiscal_year,
        "version_name": version.version_name,
        "version_number": version.version_number,
        "status": version.status,
        "is_board_approved": version.is_board_approved,
        "board_approved_at": version.board_approved_at.isoformat() if version.board_approved_at else None,
        "board_approved_by": str(version.board_approved_by) if version.board_approved_by else None,
        "notes": version.notes,
        "created_by": str(version.created_by),
        "created_at": version.created_at.isoformat(),
        "updated_at": version.updated_at.isoformat(),
        "line_item_count": line_item_count,
    }


def _serialize_line(line: BudgetLineItem) -> dict:
    monthly = [getattr(line, f"month_{i:02d}") for i in range(1, 13)]
    return {
        "id": str(line.id),
        "budget_version_id": str(line.budget_version_id),
        "tenant_id": str(line.tenant_id),
        "entity_id": str(line.entity_id) if line.entity_id else None,
        "mis_line_item": line.mis_line_item,
        "mis_category": line.mis_category,
        "monthly_values": [format(Decimal(str(value)), "f") for value in monthly],
        "annual_total": format(Decimal(str(line.annual_total)), "f"),
        "basis": line.basis,
        "created_at": line.created_at.isoformat(),
    }


def _serialize_vs_actual(payload: dict) -> dict:
    lines: list[dict] = []
    for row in payload["lines"]:
        lines.append(
            {
                "mis_line_item": row["mis_line_item"],
                "mis_category": row["mis_category"],
                "budget_ytd": format(row["budget_ytd"], "f"),
                "actual_ytd": format(row["actual_ytd"], "f"),
                "variance_amount": format(row["variance_amount"], "f"),
                "variance_pct": format(row["variance_pct"], "f"),
                "budget_full_year": format(row["budget_full_year"], "f"),
                "monthly": [
                    {
                        "month": m["month"],
                        "budget": format(m["budget"], "f"),
                        "actual": format(m["actual"], "f"),
                        "variance": format(m["variance"], "f"),
                    }
                    for m in row["monthly"]
                ],
            }
        )
    return {
        "fiscal_year": payload["fiscal_year"],
        "period_through": payload["period_through"],
        "version_id": payload["version_id"],
        "lines": lines,
        "summary": {
            "total_revenue_budget": format(payload["summary"]["total_revenue_budget"], "f"),
            "total_revenue_actual": format(payload["summary"]["total_revenue_actual"], "f"),
            "ebitda_budget": format(payload["summary"]["ebitda_budget"], "f"),
            "ebitda_actual": format(payload["summary"]["ebitda_actual"], "f"),
            "on_budget": payload["summary"]["on_budget"],
        },
    }


@router.post("/versions", status_code=status.HTTP_201_CREATED)
async def create_version(
    body: CreateVersionRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> dict:
    try:
        version = await create_budget_version(
            session,
            tenant_id=user.tenant_id,
            fiscal_year=body.fiscal_year,
            version_name=body.version_name,
            created_by=user.id,
            copy_from_version_id=body.copy_from_version_id,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
    await session.flush()
    return _serialize_version(version)


@router.get("/versions")
async def list_versions(
    fiscal_year: int | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> Paginated[dict]:
    target_year = fiscal_year or datetime.now(UTC).year
    rows = await get_budget_summary(session, user.tenant_id, target_year)
    total = len(rows)
    page = rows[offset : offset + limit]
    serialized: list[dict] = []
    for row in page:
        count = (
            await session.execute(
                select(func.count()).select_from(BudgetLineItem).where(BudgetLineItem.budget_version_id == row.id)
            )
        ).scalar_one()
        serialized.append(_serialize_version(row, line_item_count=int(count)))
    return Paginated[dict](data=serialized, total=total, limit=limit, offset=offset)


@router.get("/versions/{version_id}")
async def get_version(
    version_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    version = (
        await session.execute(
            select(BudgetVersion).where(
                BudgetVersion.id == version_id,
                BudgetVersion.tenant_id == user.tenant_id,
            )
        )
    ).scalar_one_or_none()
    if version is None:
        raise HTTPException(status_code=404, detail="Budget version not found")
    lines = (
        await session.execute(
            select(BudgetLineItem)
            .where(
                BudgetLineItem.budget_version_id == version.id,
                BudgetLineItem.tenant_id == user.tenant_id,
            )
            .order_by(BudgetLineItem.mis_category, BudgetLineItem.mis_line_item)
        )
    ).scalars().all()
    payload = _serialize_version(version, line_item_count=len(lines))
    payload["lines"] = [_serialize_line(line) for line in lines]
    return payload


@router.post("/versions/{version_id}/lines", status_code=status.HTTP_201_CREATED)
async def add_line(
    version_id: uuid.UUID,
    body: AddLineRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> dict:
    monthly_values = [_to_decimal(value, "monthly_values") for value in body.monthly_values]
    try:
        line = await upsert_budget_line(
            session,
            tenant_id=user.tenant_id,
            budget_version_id=version_id,
            mis_line_item=body.mis_line_item,
            mis_category=body.mis_category,
            monthly_values=monthly_values,
            basis=body.basis,
            entity_id=body.entity_id,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
    except (ValidationError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(getattr(exc, "message", str(exc)))) from exc
    await session.flush()
    return _serialize_line(line)


@router.post("/versions/{version_id}/approve")
async def approve(
    version_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> dict:
    try:
        version = await approve_budget(
            session,
            tenant_id=user.tenant_id,
            budget_version_id=version_id,
            approved_by=user.id,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
    await session.flush()
    return _serialize_version(version)


@router.get("/vs-actual")
async def vs_actual(
    fiscal_year: int = Query(...),
    period: str = Query(...),
    version_id: uuid.UUID | None = Query(default=None),
    entity_id: uuid.UUID | None = Query(default=None),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    try:
        payload = await get_budget_vs_actual(
            session,
            tenant_id=user.tenant_id,
            fiscal_year=fiscal_year,
            period=period,
            budget_version_id=version_id,
            entity_id=entity_id,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc
    return _serialize_vs_actual(payload)


@router.get("/vs-actual/export")
async def export_vs_actual(
    fiscal_year: int = Query(...),
    period: str = Query(...),
    version_id: uuid.UUID | None = Query(default=None),
    entity_id: uuid.UUID | None = Query(default=None),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> Response:
    try:
        payload = await get_budget_vs_actual(
            session,
            tenant_id=user.tenant_id,
            fiscal_year=fiscal_year,
            period=period,
            budget_version_id=version_id,
            entity_id=entity_id,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Budget vs Actual"
    sheet.append(["Line Item", "Category", "Budget YTD", "Actual YTD", "Variance", "Variance %"])
    for row in payload["lines"]:
        sheet.append(
            [
                row["mis_line_item"],
                row["mis_category"],
                format(row["budget_ytd"], "f"),
                format(row["actual_ytd"], "f"),
                format(row["variance_amount"], "f"),
                format(row["variance_pct"], "f"),
            ]
        )

    buffer = BytesIO()
    workbook.save(buffer)
    body = buffer.getvalue()
    filename = f"Budget_vs_Actual_{fiscal_year}_{period}.xlsx"
    return Response(
        content=body,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

