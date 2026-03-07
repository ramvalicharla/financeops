from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user
from financeops.db.models.users import IamUser
from financeops.modules.payroll_gl_normalization.api.schemas import (
    RunActionResponse,
    RunSummaryResponse,
    RunUploadRequest,
    RunUploadResponse,
    SourceCommitVersionRequest,
    SourceDetectRequest,
    SourceSummaryResponse,
    SourceVersionSummaryResponse,
)
from financeops.modules.payroll_gl_normalization.application.gl_normalization_service import (
    GlNormalizationService,
)
from financeops.modules.payroll_gl_normalization.application.mapping_service import (
    MappingService,
)
from financeops.modules.payroll_gl_normalization.application.payroll_normalization_service import (
    PayrollNormalizationService,
)
from financeops.modules.payroll_gl_normalization.application.run_service import (
    NormalizationRunService,
)
from financeops.modules.payroll_gl_normalization.application.source_detection_service import (
    SourceDetectionService,
)
from financeops.modules.payroll_gl_normalization.application.validation_service import (
    ValidationService,
)
from financeops.modules.payroll_gl_normalization.infrastructure.repository import (
    PayrollGlNormalizationRepository,
)
from financeops.modules.payroll_gl_normalization.policies.control_plane_policy import (
    normalization_control_plane_dependency,
)

router = APIRouter()


def _build_service(session: AsyncSession) -> NormalizationRunService:
    return NormalizationRunService(
        repository=PayrollGlNormalizationRepository(session),
        source_detection_service=SourceDetectionService(),
        mapping_service=MappingService(),
        payroll_normalization_service=PayrollNormalizationService(),
        gl_normalization_service=GlNormalizationService(),
        validation_service=ValidationService(),
    )


@router.post(
    "/sources/detect",
    status_code=status.HTTP_200_OK,
    dependencies=[
        Depends(
            normalization_control_plane_dependency(
                action="normalization_source_create",
                resource_type="normalization_source",
            )
        )
    ],
)
async def detect_source(
    body: SourceDetectRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    service = _build_service(session)
    try:
        return await service.detect_source(
            tenant_id=user.tenant_id,
            source_code=body.source_code,
            file_name=body.file_name,
            file_content_base64=body.file_content_base64,
            source_family_hint=body.source_family_hint,
            sheet_name=body.sheet_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/sources/commit-version",
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(
            normalization_control_plane_dependency(
                action="normalization_mapping_review",
                resource_type="normalization_mapping",
            )
        )
    ],
)
async def commit_source_version(
    body: SourceCommitVersionRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    service = _build_service(session)
    try:
        result = await service.commit_source_version(
            tenant_id=user.tenant_id,
            organisation_id=body.organisation_id,
            source_family=body.source_family,
            source_code=body.source_code,
            source_name=body.source_name,
            structure_hash=body.structure_hash,
            header_hash=body.header_hash,
            row_signature_hash=body.row_signature_hash,
            source_detection_summary_json=body.source_detection_summary_json,
            activate=body.activate,
            created_by=user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await session.commit()
    return result


@router.get(
    "/sources",
    response_model=list[SourceSummaryResponse],
    dependencies=[
        Depends(
            normalization_control_plane_dependency(
                action="normalization_extract_view",
                resource_type="normalization_source",
            )
        )
    ],
)
async def list_sources(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[SourceSummaryResponse]:
    service = _build_service(session)
    rows = await service.list_sources(tenant_id=user.tenant_id)
    return [
        SourceSummaryResponse(
            id=row.id,
            source_family=row.source_family,
            source_code=row.source_code,
            source_name=row.source_name,
            status=row.status,
            created_at=row.created_at.isoformat(),
        )
        for row in rows
    ]


@router.get(
    "/sources/{id}/versions",
    response_model=list[SourceVersionSummaryResponse],
    dependencies=[
        Depends(
            normalization_control_plane_dependency(
                action="normalization_extract_view",
                resource_type="normalization_source_version",
            )
        )
    ],
)
async def list_source_versions(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[SourceVersionSummaryResponse]:
    service = _build_service(session)
    rows = await service.list_source_versions(tenant_id=user.tenant_id, source_id=id)
    return [
        SourceVersionSummaryResponse(
            id=row.id,
            version_no=row.version_no,
            version_token=row.version_token,
            status=row.status,
            structure_hash=row.structure_hash,
            created_at=row.created_at.isoformat(),
        )
        for row in rows
    ]


@router.post(
    "/runs/upload",
    response_model=RunUploadResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(
            normalization_control_plane_dependency(
                action="normalization_run_create",
                resource_type="normalization_run",
            )
        )
    ],
)
async def upload_run(
    body: RunUploadRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> RunUploadResponse:
    service = _build_service(session)
    try:
        result = await service.upload_run(
            tenant_id=user.tenant_id,
            organisation_id=body.organisation_id,
            source_id=body.source_id,
            source_version_id=body.source_version_id,
            run_type=body.run_type,
            reporting_period=body.reporting_period,
            source_artifact_id=body.source_artifact_id,
            file_name=body.file_name,
            file_content_base64=body.file_content_base64,
            sheet_name=body.sheet_name,
            created_by=user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await session.commit()
    return RunUploadResponse(**result)


@router.post(
    "/runs/{id}/validate",
    response_model=RunActionResponse,
    dependencies=[
        Depends(
            normalization_control_plane_dependency(
                action="normalization_run_create",
                resource_type="normalization_run",
            )
        )
    ],
)
async def validate_run(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> RunActionResponse:
    service = _build_service(session)
    try:
        result = await service.validate_run(
            tenant_id=user.tenant_id,
            run_id=id,
            created_by=user.id,
        )
    except ValueError as exc:
        detail = str(exc)
        raise HTTPException(
            status_code=404 if "not found" in detail.lower() else 400, detail=detail
        ) from exc
    await session.commit()
    return RunActionResponse(**result)


@router.post(
    "/runs/{id}/finalize",
    response_model=RunActionResponse,
    dependencies=[
        Depends(
            normalization_control_plane_dependency(
                action="normalization_run_create",
                resource_type="normalization_run",
            )
        )
    ],
)
async def finalize_run(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> RunActionResponse:
    service = _build_service(session)
    try:
        result = await service.finalize_run(
            tenant_id=user.tenant_id,
            run_id=id,
            created_by=user.id,
        )
    except ValueError as exc:
        detail = str(exc)
        raise HTTPException(
            status_code=404 if "not found" in detail.lower() else 400, detail=detail
        ) from exc
    await session.commit()
    return RunActionResponse(**result)


@router.get(
    "/runs/{id}",
    dependencies=[
        Depends(
            normalization_control_plane_dependency(
                action="normalization_run_view",
                resource_type="normalization_run",
            )
        )
    ],
)
async def get_run(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    service = _build_service(session)
    row = await service.get_run(tenant_id=user.tenant_id, run_id=id)
    if row is None:
        raise HTTPException(status_code=404, detail="Normalization run not found")
    return row


@router.get(
    "/runs/{id}/exceptions",
    dependencies=[
        Depends(
            normalization_control_plane_dependency(
                action="normalization_run_view",
                resource_type="normalization_exception",
            )
        )
    ],
)
async def get_run_exceptions(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    service = _build_service(session)
    return await service.list_run_exceptions(tenant_id=user.tenant_id, run_id=id)


@router.get(
    "/runs/{id}/payroll-lines",
    dependencies=[
        Depends(
            normalization_control_plane_dependency(
                action="normalization_extract_view",
                resource_type="payroll_normalized_line",
            )
        )
    ],
)
async def get_payroll_lines(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    service = _build_service(session)
    return await service.list_payroll_lines(tenant_id=user.tenant_id, run_id=id)


@router.get(
    "/runs/{id}/gl-lines",
    dependencies=[
        Depends(
            normalization_control_plane_dependency(
                action="normalization_extract_view",
                resource_type="gl_normalized_line",
            )
        )
    ],
)
async def get_gl_lines(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    service = _build_service(session)
    return await service.list_gl_lines(tenant_id=user.tenant_id, run_id=id)


@router.get(
    "/runs/{id}/summary",
    response_model=RunSummaryResponse,
    dependencies=[
        Depends(
            normalization_control_plane_dependency(
                action="normalization_extract_view",
                resource_type="normalization_run",
            )
        )
    ],
)
async def get_run_summary(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> RunSummaryResponse:
    service = _build_service(session)
    return RunSummaryResponse(
        **(await service.run_summary(tenant_id=user.tenant_id, run_id=id))
    )
