from __future__ import annotations

import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path as ApiPath, Query, Request, Response, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user
from financeops.config import settings
from financeops.db.models.users import IamUser
from financeops.db.models.board_pack_generator import (
    BoardPackGeneratorArtifact,
    BoardPackGeneratorDefinition,
    BoardPackGeneratorRun,
    BoardPackGeneratorSection,
)
from financeops.modules.board_pack_generator.domain.enums import PeriodType, SectionType
from financeops.modules.board_pack_generator.domain.pack_definition import (
    PackDefinitionSchema,
    SectionConfig,
)
from financeops.modules.board_pack_generator.infrastructure.repository import (
    BoardPackRepository,
)
from financeops.modules.board_pack_generator.tasks import generate_board_pack_task
from financeops.shared_kernel.pagination import Paginated

router = APIRouter(prefix="/board-packs", tags=["board-packs"])


class CreateDefinitionRequest(BaseModel):
    name: str
    description: str | None = None
    section_types: list[SectionType]
    entity_ids: list[uuid.UUID]
    period_type: PeriodType
    config: dict[str, Any] = Field(default_factory=dict)


class UpdateDefinitionRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    section_types: list[SectionType] | None = None
    entity_ids: list[uuid.UUID] | None = None
    config: dict[str, Any] | None = None


class DefinitionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    description: str | None = None
    section_types: list[str]
    entity_ids: list[str]
    period_type: str
    config: dict[str, Any]
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime
    is_active: bool


class GenerateRequest(BaseModel):
    definition_id: uuid.UUID
    period_start: date
    period_end: date

    @model_validator(mode="after")
    def _validate_period_range(self) -> "GenerateRequest":
        if self.period_end < self.period_start:
            raise ValueError("period_end must be greater than or equal to period_start")
        return self


class RunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    definition_id: uuid.UUID
    period_start: date
    period_end: date
    status: str
    triggered_by: uuid.UUID
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
    chain_hash: str | None = None
    run_metadata: dict[str, Any]
    created_at: datetime


class SectionResponse(BaseModel):
    id: uuid.UUID
    run_id: uuid.UUID
    section_type: str
    section_order: int
    title: str
    section_hash: str
    rendered_at: datetime


class ArtifactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    run_id: uuid.UUID
    format: str
    storage_path: str
    file_size_bytes: int | None = None
    generated_at: datetime
    checksum: str | None = None


def _build_definition_schema(body: CreateDefinitionRequest) -> PackDefinitionSchema:
    section_configs = [
        SectionConfig(section_type=section_type, order=index + 1)
        for index, section_type in enumerate(body.section_types)
    ]
    return PackDefinitionSchema(
        name=body.name,
        description=body.description,
        section_configs=section_configs,
        entity_ids=body.entity_ids,
        period_type=body.period_type,
        config=dict(body.config or {}),
    )


@router.post("/definitions", response_model=DefinitionResponse, status_code=status.HTTP_201_CREATED)
async def create_definition(
    body: CreateDefinitionRequest,
    db: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> DefinitionResponse:
    repo = BoardPackRepository()
    row = await repo.create_definition(
        db=db,
        tenant_id=user.tenant_id,
        schema=_build_definition_schema(body),
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
    repo = BoardPackRepository()
    base_stmt = select(BoardPackGeneratorDefinition).where(
        BoardPackGeneratorDefinition.tenant_id == user.tenant_id
    )
    if active_only:
        base_stmt = base_stmt.where(BoardPackGeneratorDefinition.is_active.is_(True))
    total = (await db.execute(select(func.count()).select_from(base_stmt.subquery()))).scalar_one()
    rows = (
        await db.execute(
            base_stmt
            .order_by(BoardPackGeneratorDefinition.created_at.desc(), BoardPackGeneratorDefinition.id.desc())
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()
    if active_only and not rows:
        raise HTTPException(status_code=404, detail="No active definitions found")
    data = [DefinitionResponse.model_validate(row) for row in rows]
    if "limit" not in request.query_params and "offset" not in request.query_params:
        return data
    return Paginated[DefinitionResponse](data=data, total=int(total), limit=limit, offset=offset)


@router.get("/definitions/{definition_id}", response_model=DefinitionResponse)
async def get_definition(
    definition_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> DefinitionResponse:
    repo = BoardPackRepository()
    row = await repo.get_definition(
        db=db,
        tenant_id=user.tenant_id,
        definition_id=definition_id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Definition not found")
    return DefinitionResponse.model_validate(row)


@router.patch("/definitions/{definition_id}", response_model=DefinitionResponse)
async def update_definition(
    definition_id: uuid.UUID,
    body: UpdateDefinitionRequest,
    db: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> DefinitionResponse:
    repo = BoardPackRepository()
    existing = await repo.get_definition(
        db=db,
        tenant_id=user.tenant_id,
        definition_id=definition_id,
    )
    if existing is None:
        raise HTTPException(status_code=404, detail="Definition not found")

    updates = body.model_dump(exclude_unset=True)
    if "section_types" in updates and updates["section_types"] is not None:
        updates["section_types"] = [value.value for value in updates["section_types"]]

    row = await repo.update_definition(
        db=db,
        tenant_id=user.tenant_id,
        definition_id=definition_id,
        updates=updates,
    )
    await db.commit()
    return DefinitionResponse.model_validate(row)


@router.delete("/definitions/{definition_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_definition(
    definition_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> Response:
    repo = BoardPackRepository()
    row = await repo.get_definition(
        db=db,
        tenant_id=user.tenant_id,
        definition_id=definition_id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Definition not found")

    await repo.deactivate_definition(
        db=db,
        tenant_id=user.tenant_id,
        definition_id=definition_id,
    )
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/generate", response_model=RunResponse, status_code=status.HTTP_202_ACCEPTED)
async def generate_pack(
    body: GenerateRequest,
    db: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> RunResponse:
    repo = BoardPackRepository()
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
        period_start=body.period_start,
        period_end=body.period_end,
        triggered_by=user.id,
    )
    await db.commit()
    generate_board_pack_task.delay(str(run.id), str(user.tenant_id))
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
    repo = BoardPackRepository()
    total_stmt = select(BoardPackGeneratorRun).where(BoardPackGeneratorRun.tenant_id == user.tenant_id)
    if definition_id:
        total_stmt = total_stmt.where(BoardPackGeneratorRun.definition_id == definition_id)
    if status_filter:
        total_stmt = total_stmt.where(BoardPackGeneratorRun.status == status_filter)
    total = (await db.execute(select(func.count()).select_from(total_stmt.subquery()))).scalar_one()
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


@router.get("/runs/{run_id}", response_model=RunResponse)
async def get_run(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> RunResponse:
    repo = BoardPackRepository()
    row = await repo.get_run(db=db, tenant_id=user.tenant_id, run_id=run_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return RunResponse.model_validate(row)


@router.get("/runs/{run_id}/sections", response_model=Paginated[SectionResponse] | list[SectionResponse])
async def list_sections(
    request: Request,
    run_id: uuid.UUID,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> Paginated[SectionResponse] | list[SectionResponse]:
    repo = BoardPackRepository()
    run = await repo.get_run(db=db, tenant_id=user.tenant_id, run_id=run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    total = (
        await db.execute(
            select(func.count()).select_from(
                select(BoardPackGeneratorSection).where(
                    BoardPackGeneratorSection.tenant_id == user.tenant_id,
                    BoardPackGeneratorSection.run_id == run_id,
                ).subquery()
            )
        )
    ).scalar_one()
    rows = (
        await db.execute(
            select(BoardPackGeneratorSection)
            .where(
                BoardPackGeneratorSection.tenant_id == user.tenant_id,
                BoardPackGeneratorSection.run_id == run_id,
            )
            .order_by(
                BoardPackGeneratorSection.section_order.asc(),
                BoardPackGeneratorSection.id.asc(),
            )
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()
    responses: list[SectionResponse] = []
    for row in rows:
        snapshot = row.data_snapshot if isinstance(row.data_snapshot, dict) else {}
        title = str(snapshot.get("title") or row.section_type.replace("_", " ").title())
        responses.append(
            SectionResponse(
                id=row.id,
                run_id=row.run_id,
                section_type=row.section_type,
                section_order=row.section_order,
                title=title,
                section_hash=row.section_hash,
                rendered_at=row.rendered_at,
            )
        )
    if "limit" not in request.query_params and "offset" not in request.query_params:
        return responses
    return Paginated[SectionResponse](data=responses, total=int(total), limit=limit, offset=offset)


@router.get("/runs/{run_id}/artifacts", response_model=Paginated[ArtifactResponse] | list[ArtifactResponse])
async def list_artifacts(
    request: Request,
    run_id: uuid.UUID,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> Paginated[ArtifactResponse] | list[ArtifactResponse]:
    repo = BoardPackRepository()
    run = await repo.get_run(db=db, tenant_id=user.tenant_id, run_id=run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    total = (
        await db.execute(
            select(func.count()).select_from(
                select(BoardPackGeneratorArtifact).where(
                    BoardPackGeneratorArtifact.tenant_id == user.tenant_id,
                    BoardPackGeneratorArtifact.run_id == run_id,
                ).subquery()
            )
        )
    ).scalar_one()
    rows = (
        await db.execute(
            select(BoardPackGeneratorArtifact)
            .where(
                BoardPackGeneratorArtifact.tenant_id == user.tenant_id,
                BoardPackGeneratorArtifact.run_id == run_id,
            )
            .order_by(
                BoardPackGeneratorArtifact.generated_at.desc(),
                BoardPackGeneratorArtifact.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()
    data = [ArtifactResponse.model_validate(row) for row in rows]
    if "limit" not in request.query_params and "offset" not in request.query_params:
        return data
    return Paginated[ArtifactResponse](data=data, total=int(total), limit=limit, offset=offset)


@router.get("/runs/{run_id}/download/{format}")
async def download_artifact(
    run_id: uuid.UUID,
    format: str = ApiPath(..., pattern="(?i)^(pdf|excel)$"),
    db: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> FileResponse:
    repo = BoardPackRepository()
    run = await repo.get_run(db=db, tenant_id=user.tenant_id, run_id=run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    requested_format = format.upper()
    artifacts = await repo.list_artifacts_for_run(db=db, tenant_id=user.tenant_id, run_id=run_id)
    artifact = next((row for row in artifacts if row.format.upper() == requested_format), None)
    if artifact is None:
        raise HTTPException(status_code=404, detail=f"{requested_format} artifact not found for run")

    base_dir = Path(str(getattr(settings, "ARTIFACTS_BASE_DIR", "artifacts")))
    file_path = base_dir / artifact.storage_path
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Artifact file not found in storage")

    media_type = (
        "application/pdf"
        if requested_format == "PDF"
        else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    download_name = f"board_pack_{run.period_start.isoformat()}_{run.period_end.isoformat()}.{ 'pdf' if requested_format == 'PDF' else 'xlsx' }"
    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=download_name,
    )
