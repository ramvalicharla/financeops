from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user
from financeops.db.models.accounting_notifications import AccountingAuditExportRun
from financeops.db.models.users import IamUser
from financeops.modules.accounting_layer.application.ap_ageing_service import (
    export_ap_ageing_csv,
    get_ap_ageing_summary,
)
from financeops.modules.accounting_layer.application.approval_service import (
    get_sla_metrics,
)
from financeops.modules.accounting_layer.application.audit_export_service import (
    create_audit_export,
)

reporting_router = APIRouter(tags=["Accounting Reporting"])


class AuditExportRequest(BaseModel):
    export_type: str
    export_format: str = "CSV"
    entity_id: uuid.UUID | None = None
    fiscal_year: int | None = None
    fiscal_period_from: int | None = None
    fiscal_period_to: int | None = None
    date_from: date | None = None
    date_to: date | None = None
    filters: dict[str, Any] | None = None


class AuditExportResponse(BaseModel):
    export_run_id: uuid.UUID
    status: str
    export_type: str
    export_format: str
    row_count: int | None
    r2_key: str | None


@reporting_router.get("/sla/metrics")
async def sla_metrics_endpoint(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    user: IamUser = Depends(get_current_user),
    entity_id: uuid.UUID | None = Query(default=None),
    fiscal_year: int | None = Query(default=None),
    fiscal_period: int | None = Query(default=None),
) -> dict[str, Any]:
    del request
    return await get_sla_metrics(
        session,
        tenant_id=user.tenant_id,
        entity_id=entity_id,
        fiscal_year=fiscal_year,
        fiscal_period=fiscal_period,
    )


@reporting_router.get("/ap-ageing/summary")
async def ap_ageing_summary_endpoint(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    user: IamUser = Depends(get_current_user),
    entity_id: uuid.UUID = Query(...),
    snapshot_date: date = Query(...),
    vendor_id: uuid.UUID | None = Query(default=None),
) -> dict[str, Any]:
    del request
    return await get_ap_ageing_summary(
        session,
        tenant_id=user.tenant_id,
        entity_id=entity_id,
        snapshot_date=snapshot_date,
        vendor_id=vendor_id,
    )


@reporting_router.get("/ap-ageing/export")
async def ap_ageing_export_endpoint(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    user: IamUser = Depends(get_current_user),
    entity_id: uuid.UUID = Query(...),
    date_from: date = Query(...),
    date_to: date = Query(...),
    vendor_id: uuid.UUID | None = Query(default=None),
) -> Response:
    del request
    csv_content = await export_ap_ageing_csv(
        session,
        tenant_id=user.tenant_id,
        entity_id=entity_id,
        date_from=date_from,
        date_to=date_to,
        vendor_id=vendor_id,
    )
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=ap_ageing_{date_from}_{date_to}.csv",
        },
    )


@reporting_router.post("/audit/export", response_model=AuditExportResponse)
async def audit_export_endpoint(
    request: Request,
    body: AuditExportRequest,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    user: IamUser = Depends(get_current_user),
) -> AuditExportResponse:
    del request
    run = await create_audit_export(
        session,
        tenant_id=user.tenant_id,
        entity_id=body.entity_id,
        export_type=body.export_type,
        export_format=body.export_format,
        requested_by=user.id,
        fiscal_year=body.fiscal_year,
        fiscal_period_from=body.fiscal_period_from,
        fiscal_period_to=body.fiscal_period_to,
        date_from=body.date_from,
        date_to=body.date_to,
        filters=body.filters,
    )
    await session.flush()
    return AuditExportResponse(
        export_run_id=run.id,
        status=run.status,
        export_type=run.export_type,
        export_format=run.export_format,
        row_count=run.row_count,
        r2_key=run.r2_key,
    )


@reporting_router.get("/audit/exports")
async def list_audit_exports_endpoint(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    user: IamUser = Depends(get_current_user),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[dict[str, Any]]:
    del request
    stmt = (
        select(AccountingAuditExportRun)
        .where(AccountingAuditExportRun.tenant_id == user.tenant_id)
        .order_by(AccountingAuditExportRun.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = list((await session.execute(stmt)).scalars().all())
    return [
        {
            "id": str(row.id),
            "export_type": row.export_type,
            "export_format": row.export_format,
            "status": row.status,
            "row_count": row.row_count,
            "r2_key": row.r2_key,
            "created_at": row.created_at.isoformat(),
            "completed_at": row.completed_at.isoformat() if row.completed_at else None,
        }
        for row in rows
    ]

