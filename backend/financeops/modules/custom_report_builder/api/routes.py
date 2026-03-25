from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path as ApiPath, Query, Request, Response, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user
from financeops.config import settings
from financeops.db.models.custom_report_builder import (
    ReportDefinition,
    ReportRun,
)
from financeops.db.models.users import IamUser
from financeops.modules.custom_report_builder.domain.enums import (
    ReportExportFormat,
)
from financeops.modules.custom_report_builder.domain.filter_dsl import (
    FilterConfig,
    ReportDefinitionSchema,
    SortConfig,
)
from financeops.modules.custom_report_builder.domain.metric_registry import (
    MetricDefinition,
    list_metrics,
)
from financeops.modules.custom_report_builder.infrastructure.repository import (
    ReportRepository,
)
from financeops.modules.custom_report_builder.tasks import run_custom_report_task
from financeops.shared_kernel.pagination import Paginated

router = APIRouter(prefix="/reports", tags=["reports"])


class CreateDefinitionRequest(BaseModel):
    name: str
    description: str | None = None
    metric_keys: list[str]
    filter_config: FilterConfig = Field(default_factory=FilterConfig)
    group_by: list[str] = Field(default_factory=list)
    sort_config: SortConfig | None = None
    export_formats: list[ReportExportFormat] = Field(default_factory=lambda: [ReportExportFormat.CSV])
    config: dict[str, Any] = Field(default_factory=dict)


class UpdateDefinitionRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    metric_keys: list[str] | None = None
    filter_config: FilterConfig | None = None
    group_by: list[str] | None = None
    sort_config: SortConfig | None = None
    export_formats: list[ReportExportFormat] | None = None
    config: dict[str, Any] | None = None


class DefinitionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    description: str | None = None
    metric_keys: list[str]
    filter_config: dict[str, Any]
    group_by: list[str]
    sort_config: dict[str, Any]
    export_formats: list[str]
    config: dict[str, Any]
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime
    is_active: bool


class RunRequest(BaseModel):
    definition_id: uuid.UUID
    triggered_by: uuid.UUID | None = None


class RunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    definition_id: uuid.UUID
    status: str
    triggered_by: uuid.UUID
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
    row_count: int | None = None
    run_metadata: dict[str, Any]
    created_at: datetime


class ResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    run_id: uuid.UUID
    result_data: list[dict[str, Any]] | dict[str, Any]
    result_hash: str
    export_path_csv: str | None = None
    export_path_excel: str | None = None
    export_path_pdf: str | None = None
    created_at: datetime


def _to_definition_schema(body: CreateDefinitionRequest) -> ReportDefinitionSchema:
    return ReportDefinitionSchema(
        name=body.name,
        description=body.description,
        metric_keys=body.metric_keys,
        filter_config=body.filter_config,
        group_by=body.group_by,
        sort_config=body.sort_config,
        export_formats=body.export_formats,
        config=body.config,
    )


@router.post("/definitions", response_model=DefinitionResponse, status_code=status.HTTP_201_CREATED)
async def create_definition(
    body: CreateDefinitionRequest,
    db: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> DefinitionResponse:
    repo = ReportRepository()
    try:
        schema = _to_definition_schema(body)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc
    row = await repo.create_definition(
        db=db,
        tenant_id=user.tenant_id,
        schema=schema,
        created_by=user.id,
    )
    await db.commit()
    return DefinitionResponse.model_validate(row)


@router.get("/definitions", response_model=Paginated[DefinitionResponse] | list[DefinitionResponse])
async def list_definitions(
    request: Request,
    active_only: bool = Query(default=True),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> Paginated[DefinitionResponse] | list[DefinitionResponse]:
    repo = ReportRepository()
    base_stmt = select(ReportDefinition).where(ReportDefinition.tenant_id == user.tenant_id)
    if active_only:
        base_stmt = base_stmt.where(ReportDefinition.is_active.is_(True))
    total = (await db.execute(select(func.count()).select_from(base_stmt.subquery()))).scalar_one()
    rows = (
        await db.execute(
            base_stmt
            .order_by(ReportDefinition.created_at.desc(), ReportDefinition.id.desc())
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()
    data = [DefinitionResponse.model_validate(row) for row in rows]
    if "limit" not in request.query_params and "offset" not in request.query_params:
        return data
    return Paginated[DefinitionResponse](data=data, total=int(total), limit=limit, offset=offset)


@router.get("/definitions/{id}", response_model=DefinitionResponse)
async def get_definition(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> DefinitionResponse:
    repo = ReportRepository()
    row = await repo.get_definition(db=db, tenant_id=user.tenant_id, definition_id=id)
    if row is None:
        raise HTTPException(status_code=404, detail="Definition not found")
    return DefinitionResponse.model_validate(row)


@router.patch("/definitions/{id}", response_model=DefinitionResponse)
async def update_definition(
    id: uuid.UUID,
    body: UpdateDefinitionRequest,
    db: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> DefinitionResponse:
    repo = ReportRepository()
    existing = await repo.get_definition(db=db, tenant_id=user.tenant_id, definition_id=id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Definition not found")

    updates = body.model_dump(exclude_unset=True)
    if "filter_config" in updates and updates["filter_config"] is not None:
        updates["filter_config"] = updates["filter_config"]
    if "sort_config" in updates and updates["sort_config"] is not None:
        updates["sort_config"] = updates["sort_config"]
    if "export_formats" in updates and updates["export_formats"] is not None:
        updates["export_formats"] = [fmt.value for fmt in updates["export_formats"]]

    row = await repo.update_definition(
        db=db,
        tenant_id=user.tenant_id,
        definition_id=id,
        updates=updates,
    )
    await db.commit()
    return DefinitionResponse.model_validate(row)


@router.delete("/definitions/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_definition(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> Response:
    repo = ReportRepository()
    row = await repo.get_definition(db=db, tenant_id=user.tenant_id, definition_id=id)
    if row is None:
        raise HTTPException(status_code=404, detail="Definition not found")
    await repo.deactivate_definition(db=db, tenant_id=user.tenant_id, definition_id=id)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/run", response_model=RunResponse, status_code=status.HTTP_202_ACCEPTED)
async def run_report(
    body: RunRequest,
    db: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> RunResponse:
    repo = ReportRepository()
    definition = await repo.get_definition(
        db=db,
        tenant_id=user.tenant_id,
        definition_id=body.definition_id,
    )
    if definition is None:
        raise HTTPException(status_code=404, detail="Definition not found")
    if not definition.is_active:
        raise HTTPException(status_code=400, detail="Definition is inactive")

    run = await repo.create_run(
        db=db,
        tenant_id=user.tenant_id,
        definition_id=body.definition_id,
        triggered_by=body.triggered_by or user.id,
    )
    await db.commit()
    run_custom_report_task.delay(str(run.id), str(user.tenant_id))
    return RunResponse.model_validate(run)


@router.get("/runs", response_model=Paginated[RunResponse] | list[RunResponse])
async def list_runs(
    request: Request,
    definition_id: uuid.UUID | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> Paginated[RunResponse] | list[RunResponse]:
    repo = ReportRepository()
    base_stmt = select(ReportRun).where(ReportRun.tenant_id == user.tenant_id)
    if definition_id:
        base_stmt = base_stmt.where(ReportRun.definition_id == definition_id)
    if status_filter:
        base_stmt = base_stmt.where(ReportRun.status == status_filter)
    total = (await db.execute(select(func.count()).select_from(base_stmt.subquery()))).scalar_one()
    rows = await repo.list_runs(
        db=db,
        tenant_id=user.tenant_id,
        definition_id=definition_id,
        status=status_filter,
        limit=limit + offset,
    )
    paged_rows = rows[offset : offset + limit]
    data = [RunResponse.model_validate(row) for row in paged_rows]
    if "limit" not in request.query_params and "offset" not in request.query_params:
        return data
    return Paginated[RunResponse](data=data, total=int(total), limit=limit, offset=offset)


@router.get("/runs/{id}", response_model=RunResponse)
async def get_run(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> RunResponse:
    repo = ReportRepository()
    row = await repo.get_run(db=db, tenant_id=user.tenant_id, run_id=id)
    if row is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return RunResponse.model_validate(row)


@router.get("/runs/{id}/result", response_model=ResultResponse)
async def get_result(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> ResultResponse:
    repo = ReportRepository()
    run = await repo.get_run(db=db, tenant_id=user.tenant_id, run_id=id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    result = await repo.get_result_for_run(db=db, tenant_id=user.tenant_id, run_id=id)
    if result is None:
        raise HTTPException(status_code=404, detail="Result not found")
    return ResultResponse.model_validate(result)


@router.get("/runs/{id}/download/{fmt}")
async def download_result(
    id: uuid.UUID,
    fmt: str = ApiPath(..., pattern="(?i)^(csv|excel|pdf)$"),
    db: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> FileResponse:
    repo = ReportRepository()
    run = await repo.get_run(db=db, tenant_id=user.tenant_id, run_id=id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    result = await repo.get_result_for_run(db=db, tenant_id=user.tenant_id, run_id=id)
    if result is None:
        raise HTTPException(status_code=404, detail="Result not found")

    requested = fmt.upper()
    if requested == "CSV":
        storage_path = result.export_path_csv
        media_type = "text/csv"
        suffix = "csv"
    elif requested == "EXCEL":
        storage_path = result.export_path_excel
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        suffix = "xlsx"
    else:
        storage_path = result.export_path_pdf
        media_type = "application/pdf"
        suffix = "pdf"

    if not storage_path:
        raise HTTPException(status_code=404, detail=f"{requested} export not found")

    base_dir = Path(str(getattr(settings, "ARTIFACTS_BASE_DIR", "artifacts")))
    file_path = base_dir / storage_path
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Export file not found in storage")

    filename = f"report_{id}.{suffix}"
    return FileResponse(path=file_path, media_type=media_type, filename=filename)


@router.get("/metrics", response_model=Paginated[MetricDefinition] | list[MetricDefinition])
async def get_metrics(
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: IamUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> Paginated[MetricDefinition] | list[MetricDefinition]:
    _ = (current_user, session)
    rows = list_metrics()
    total = len(rows)
    paged_rows = rows[offset : offset + limit]
    if "limit" not in request.query_params and "offset" not in request.query_params:
        return paged_rows
    return Paginated[MetricDefinition](data=paged_rows, total=total, limit=limit, offset=offset)
