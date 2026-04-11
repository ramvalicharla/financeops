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
from financeops.core.intent.api import build_idempotency_key, build_intent_actor
from financeops.core.intent.enums import IntentType
from financeops.core.intent.service import IntentService
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
from financeops.platform.services.control_plane.phase4_service import Phase4ControlPlaneService
from financeops.modules.custom_report_builder.tasks import run_custom_report_task  # compatibility import
from financeops.shared_kernel.pagination import Paginated

router = APIRouter(prefix="/reports", tags=["reports"])


def _intent_payload_from_schema(schema: ReportDefinitionSchema) -> dict[str, Any]:
    payload = schema.model_dump(mode="json")
    payload["entity_ids"] = [str(entity_id) for entity_id in schema.filter_config.entity_ids]
    return payload


async def _submit_intent(
    request: Request,
    db: AsyncSession,
    *,
    user: IamUser,
    intent_type: IntentType,
    payload: dict[str, Any],
    target_id: uuid.UUID | None = None,
):
    service = IntentService(db)
    return await service.submit_intent(
        intent_type=intent_type,
        actor=build_intent_actor(request, user),
        payload=payload,
        target_id=target_id,
        idempotency_key=build_idempotency_key(
            request,
            intent_type=intent_type,
            actor=user,
            body=payload,
            target_id=target_id,
        ),
    )


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
    intent_id: uuid.UUID | None = None
    job_id: uuid.UUID | None = None


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
    intent_id: uuid.UUID | None = None
    job_id: uuid.UUID | None = None
    determinism_hash: str | None = None
    snapshot_refs: list[str] = Field(default_factory=list)
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
    snapshot_refs: list[str] = Field(default_factory=list)
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


async def _snapshot_refs(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    subject_type: str,
    subject_id: uuid.UUID,
) -> list[str]:
    snapshots = await Phase4ControlPlaneService(db).list_subject_snapshots(
        tenant_id=tenant_id,
        subject_type=subject_type,
        subject_id=str(subject_id),
        limit=10,
    )
    return [str(row["snapshot_id"]) for row in snapshots]


async def _build_definition_response(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    row: ReportDefinition,
    intent_id: uuid.UUID | None = None,
    job_id: uuid.UUID | None = None,
) -> DefinitionResponse:
    return DefinitionResponse.model_validate(row).model_copy(
        update={
            "intent_id": intent_id,
            "job_id": job_id,
        }
    )


async def _build_run_response(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    row: ReportRun,
    intent_id: uuid.UUID | None = None,
    job_id: uuid.UUID | None = None,
) -> RunResponse:
    result = await ReportRepository().get_result_for_run(db=db, tenant_id=tenant_id, run_id=row.id)
    return RunResponse.model_validate(row).model_copy(
        update={
            "intent_id": intent_id,
            "job_id": job_id,
            "determinism_hash": result.result_hash if result is not None else None,
            "snapshot_refs": await _snapshot_refs(
                db,
                tenant_id=tenant_id,
                subject_type="report_run",
                subject_id=row.id,
            ),
        }
    )


@router.post("/definitions", response_model=DefinitionResponse, status_code=status.HTTP_201_CREATED)
async def create_definition(
    request: Request,
    body: CreateDefinitionRequest,
    db: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> DefinitionResponse:
    try:
        schema = _to_definition_schema(body)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc
    result = await _submit_intent(
        request,
        db,
        user=user,
        intent_type=IntentType.CREATE_REPORT_DEFINITION,
        payload=_intent_payload_from_schema(schema),
    )
    repo = ReportRepository()
    row = await repo.get_definition(
        db=db,
        tenant_id=user.tenant_id,
        definition_id=uuid.UUID(str((result.record_refs or {})["definition_id"])),
    )
    if row is None:
        raise HTTPException(status_code=500, detail="Definition was not created")
    return await _build_definition_response(
        db,
        tenant_id=user.tenant_id,
        row=row,
        intent_id=result.intent_id,
        job_id=result.job_id,
    )


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
    return await _build_definition_response(db, tenant_id=user.tenant_id, row=row)


@router.patch("/definitions/{id}", response_model=DefinitionResponse)
async def update_definition(
    request: Request,
    id: uuid.UUID,
    body: UpdateDefinitionRequest,
    db: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> DefinitionResponse:
    repo = ReportRepository()
    existing = await repo.get_definition(db=db, tenant_id=user.tenant_id, definition_id=id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Definition not found")

    updates = body.model_dump(exclude_unset=True, mode="json")
    result = await _submit_intent(
        request,
        db,
        user=user,
        intent_type=IntentType.UPDATE_REPORT_DEFINITION,
        target_id=id,
        payload={
            "entity_ids": [str(entity_id) for entity_id in existing.filter_config.get("entity_ids", [])],
            "updates": updates,
        },
    )
    row = await repo.get_definition(db=db, tenant_id=user.tenant_id, definition_id=id)
    if row is None:
        raise HTTPException(status_code=500, detail="Definition update did not persist")
    return await _build_definition_response(
        db,
        tenant_id=user.tenant_id,
        row=row,
        intent_id=result.intent_id,
        job_id=result.job_id,
    )


@router.post("/definitions/{id}/deactivate", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_definition(
    request: Request,
    id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> Response:
    repo = ReportRepository()
    row = await repo.get_definition(db=db, tenant_id=user.tenant_id, definition_id=id)
    if row is None:
        raise HTTPException(status_code=404, detail="Definition not found")
    await _submit_intent(
        request,
        db,
        user=user,
        intent_type=IntentType.DEACTIVATE_REPORT_DEFINITION,
        target_id=id,
        payload={
            "definition_id": str(id),
            "entity_ids": [str(entity_id) for entity_id in row.filter_config.get("entity_ids", [])],
        },
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/run", response_model=RunResponse, status_code=status.HTTP_202_ACCEPTED)
async def run_report(
    request: Request,
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

    result = await _submit_intent(
        request,
        db,
        user=user,
        intent_type=IntentType.GENERATE_REPORT,
        payload={
            "definition_id": str(body.definition_id),
            "triggered_by": str(body.triggered_by or user.id),
        },
    )
    run = await repo.get_run(
        db=db,
        tenant_id=user.tenant_id,
        run_id=uuid.UUID(str((result.record_refs or {})["run_id"])),
    )
    if run is None:
        raise HTTPException(status_code=500, detail="Report run was not created")
    return await _build_run_response(
        db,
        tenant_id=user.tenant_id,
        row=run,
        intent_id=result.intent_id,
        job_id=result.job_id,
    )


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
    data = [await _build_run_response(db, tenant_id=user.tenant_id, row=row) for row in paged_rows]
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
    return await _build_run_response(db, tenant_id=user.tenant_id, row=row)


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
    return ResultResponse.model_validate(result).model_copy(
        update={
            "snapshot_refs": await _snapshot_refs(
                db,
                tenant_id=user.tenant_id,
                subject_type="report_run",
                subject_id=id,
            )
        }
    )


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
