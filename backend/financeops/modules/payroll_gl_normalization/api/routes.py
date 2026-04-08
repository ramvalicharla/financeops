from __future__ import annotations

import hashlib
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user
from financeops.core.governance.airlock import AirlockActor, AirlockAdmissionService
from financeops.core.intent.enums import IntentSourceChannel, IntentType
from financeops.core.intent.service import IntentActor, IntentService
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
from financeops.shared_kernel.pagination import Paginated

router = APIRouter()


def _upload_idempotency_key(*, tenant_id: uuid.UUID, source_id: uuid.UUID, source_version_id: uuid.UUID, reporting_period: str, file_name: str) -> str:
    seed = f"{tenant_id}:{source_id}:{source_version_id}:{reporting_period}:{file_name}"
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


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
        raise HTTPException(status_code=400, detail="internal_error") from exc


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
        raise HTTPException(status_code=400, detail="internal_error") from exc
    await session.flush()
    return result


@router.get(
    "/sources",
    response_model=Paginated[SourceSummaryResponse] | list[SourceSummaryResponse],
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
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> Paginated[SourceSummaryResponse] | list[SourceSummaryResponse]:
    service = _build_service(session)
    rows = await service.list_sources(tenant_id=user.tenant_id)
    data = [
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
    if "limit" not in request.query_params and "offset" not in request.query_params:
        return data
    return Paginated[SourceSummaryResponse](
        data=data[offset : offset + limit],
        total=len(data),
        limit=limit,
        offset=offset,
    )


@router.get(
    "/sources/{id}/versions",
    response_model=Paginated[SourceVersionSummaryResponse] | list[SourceVersionSummaryResponse],
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
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> Paginated[SourceVersionSummaryResponse] | list[SourceVersionSummaryResponse]:
    service = _build_service(session)
    rows = await service.list_source_versions(tenant_id=user.tenant_id, source_id=id)
    data = [
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
    if "limit" not in request.query_params and "offset" not in request.query_params:
        return data
    return Paginated[SourceVersionSummaryResponse](
        data=data[offset : offset + limit],
        total=len(data),
        limit=limit,
        offset=offset,
    )


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
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> RunUploadResponse:
    airlock_service = AirlockAdmissionService()
    try:
        import base64

        content = base64.b64decode(body.file_content_base64)
        airlock_result = await airlock_service.submit_external_input(
            session,
            source_type="normalization_upload",
            actor=AirlockActor(user_id=user.id, tenant_id=user.tenant_id, role=user.role.value),
            metadata={
                "source_id": str(body.source_id),
                "source_version_id": str(body.source_version_id),
                "run_type": body.run_type,
                "reporting_period": body.reporting_period.isoformat(),
            },
            content=content,
            file_name=body.file_name,
            source_reference=str(body.source_id),
            idempotency_key=f"{user.tenant_id}:{body.source_id}:{body.source_version_id}:{body.reporting_period}:{body.file_name}",
        )
        airlock_result = await airlock_service.admit_airlock_item(
            session,
            item_id=airlock_result.item_id,
            actor=AirlockActor(user_id=user.id, tenant_id=user.tenant_id, role=user.role.value),
        )
        result = await IntentService(session).submit_intent(
            intent_type=IntentType.CREATE_NORMALIZATION_RUN,
            actor=IntentActor(
                user_id=user.id,
                tenant_id=user.tenant_id,
                role=user.role.value,
                source_channel=IntentSourceChannel.API.value,
                request_id=str(getattr(request.state, "request_id", "") or "") or None,
                correlation_id=str(getattr(request.state, "correlation_id", "") or "") or None,
            ),
            payload={
                "organisation_id": str(body.organisation_id),
                "entity_id": None,
                "source_id": str(body.source_id),
                "source_version_id": str(body.source_version_id),
                "run_type": body.run_type,
                "reporting_period": body.reporting_period.isoformat(),
                "source_artifact_id": str(body.source_artifact_id),
                "file_name": body.file_name,
                "file_content_base64": body.file_content_base64,
                "sheet_name": body.sheet_name,
                "admitted_airlock_item_id": str(airlock_result.item_id),
                "source_type": "normalization_upload",
                "source_external_ref": str(body.source_id),
            },
            idempotency_key=_upload_idempotency_key(
                tenant_id=user.tenant_id,
                source_id=body.source_id,
                source_version_id=body.source_version_id,
                reporting_period=body.reporting_period.isoformat(),
                file_name=body.file_name,
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="internal_error") from exc
    await session.flush()
    record_refs = result.record_refs or {}
    return RunUploadResponse(
        run_id=uuid.UUID(str(record_refs["run_id"])),
        run_token=str(record_refs["run_token"]),
        run_status=str(record_refs["run_status"]),
        idempotent=bool(record_refs["idempotent"]),
        intent_id=result.intent_id,
        job_id=result.job_id or uuid.UUID(int=0),
        payroll_line_count=int(record_refs.get("payroll_line_count", 0)),
        gl_line_count=int(record_refs.get("gl_line_count", 0)),
        exception_count=int(record_refs.get("exception_count", 0)),
        source_airlock_item_id=(
            uuid.UUID(str(record_refs["source_airlock_item_id"]))
            if record_refs.get("source_airlock_item_id")
            else None
        ),
    )


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
    await session.flush()
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
    await session.flush()
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
