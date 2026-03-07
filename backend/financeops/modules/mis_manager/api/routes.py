from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user
from financeops.db.models.users import IamUser
from financeops.modules.mis_manager.api.schemas import (
    SnapshotStatusActionResponse,
    SnapshotUploadRequest,
    SnapshotUploadResponse,
    TemplateCommitVersionRequest,
    TemplateDetectRequest,
    TemplateSummaryResponse,
    TemplateVersionSummaryResponse,
)
from financeops.modules.mis_manager.application.canonical_dictionary_service import (
    CanonicalDictionaryService,
)
from financeops.modules.mis_manager.application.drift_detection_service import (
    DriftDetectionService,
)
from financeops.modules.mis_manager.application.ingest_service import MisIngestService
from financeops.modules.mis_manager.application.mapping_service import MappingService
from financeops.modules.mis_manager.application.snapshot_service import SnapshotService
from financeops.modules.mis_manager.application.template_detection_service import (
    TemplateDetectionService,
)
from financeops.modules.mis_manager.application.validation_service import (
    ValidationService,
)
from financeops.modules.mis_manager.infrastructure.repository import (
    MisManagerRepository,
)
from financeops.modules.mis_manager.policies.control_plane_policy import (
    mis_control_plane_dependency,
)

router = APIRouter()


def _build_service(session: AsyncSession) -> MisIngestService:
    dictionary_service = CanonicalDictionaryService()
    mapping_service = MappingService(dictionary_service)
    drift_service = DriftDetectionService()
    template_detection_service = TemplateDetectionService(drift_service)
    snapshot_service = SnapshotService(mapping_service)
    validation_service = ValidationService()
    repository = MisManagerRepository(session)
    return MisIngestService(
        repository=repository,
        template_detection_service=template_detection_service,
        mapping_service=mapping_service,
        snapshot_service=snapshot_service,
        validation_service=validation_service,
    )


@router.post(
    "/templates/detect",
    status_code=status.HTTP_200_OK,
    dependencies=[
        Depends(
            mis_control_plane_dependency(
                action="mis_template_create", resource_type="mis_template"
            )
        )
    ],
)
async def detect_template(
    body: TemplateDetectRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    service = _build_service(session)
    try:
        result = await service.detect_template(
            tenant_id=user.tenant_id,
            template_code=body.template_code,
            file_name=body.file_name,
            file_content_base64=body.file_content_base64,
            sheet_name=body.sheet_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result


@router.post(
    "/templates/commit-version",
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(
            mis_control_plane_dependency(
                action="mis_template_review", resource_type="mis_template_version"
            )
        )
    ],
)
async def commit_template_version(
    body: TemplateCommitVersionRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    service = _build_service(session)
    try:
        result = await service.commit_template_version(
            tenant_id=user.tenant_id,
            organisation_id=body.organisation_id,
            template_code=body.template_code,
            template_name=body.template_name,
            template_type=body.template_type,
            created_by=user.id,
            structure_hash=body.structure_hash,
            header_hash=body.header_hash,
            row_signature_hash=body.row_signature_hash,
            column_signature_hash=body.column_signature_hash,
            detection_summary_json=body.detection_summary_json,
            drift_reason=body.drift_reason,
            activate=body.activate,
            effective_from=body.effective_from,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await session.commit()
    return result


@router.post(
    "/snapshots/upload",
    response_model=SnapshotUploadResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(
            mis_control_plane_dependency(
                action="mis_snapshot_upload", resource_type="mis_snapshot"
            )
        )
    ],
)
async def upload_snapshot(
    body: SnapshotUploadRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> SnapshotUploadResponse:
    service = _build_service(session)
    try:
        result = await service.upload_snapshot(
            tenant_id=user.tenant_id,
            organisation_id=body.organisation_id,
            template_id=body.template_id,
            template_version_id=body.template_version_id,
            reporting_period=body.reporting_period,
            upload_artifact_id=body.upload_artifact_id,
            file_name=body.file_name,
            file_content_base64=body.file_content_base64,
            sheet_name=body.sheet_name,
            currency_code=body.currency_code,
            created_by=user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await session.commit()
    return SnapshotUploadResponse(**result)


@router.post(
    "/snapshots/{id}/validate",
    response_model=SnapshotStatusActionResponse,
    dependencies=[
        Depends(
            mis_control_plane_dependency(
                action="mis_snapshot_finalize", resource_type="mis_snapshot"
            )
        )
    ],
)
async def validate_snapshot(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> SnapshotStatusActionResponse:
    service = _build_service(session)
    try:
        result = await service.validate_snapshot(
            tenant_id=user.tenant_id,
            snapshot_id=id,
            created_by=user.id,
        )
    except ValueError as exc:
        detail = str(exc)
        raise HTTPException(
            status_code=404 if "not found" in detail.lower() else 400, detail=detail
        ) from exc
    await session.commit()
    return SnapshotStatusActionResponse(**result)


@router.post(
    "/snapshots/{id}/finalize",
    response_model=SnapshotStatusActionResponse,
    dependencies=[
        Depends(
            mis_control_plane_dependency(
                action="mis_snapshot_finalize", resource_type="mis_snapshot"
            )
        )
    ],
)
async def finalize_snapshot(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> SnapshotStatusActionResponse:
    service = _build_service(session)
    try:
        result = await service.finalize_snapshot(
            tenant_id=user.tenant_id,
            snapshot_id=id,
            created_by=user.id,
        )
    except ValueError as exc:
        detail = str(exc)
        raise HTTPException(
            status_code=404 if "not found" in detail.lower() else 400, detail=detail
        ) from exc
    await session.commit()
    return SnapshotStatusActionResponse(**result)


@router.get(
    "/templates",
    response_model=list[TemplateSummaryResponse],
    dependencies=[
        Depends(
            mis_control_plane_dependency(
                action="mis_snapshot_view", resource_type="mis_template"
            )
        )
    ],
)
async def list_templates(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[TemplateSummaryResponse]:
    service = _build_service(session)
    templates = await service.list_templates(tenant_id=user.tenant_id)
    return [
        TemplateSummaryResponse(
            id=row.id,
            template_code=row.template_code,
            template_name=row.template_name,
            template_type=row.template_type,
            status=row.status,
            created_at=row.created_at.isoformat(),
        )
        for row in templates
    ]


@router.get(
    "/templates/{id}/versions",
    response_model=list[TemplateVersionSummaryResponse],
    dependencies=[
        Depends(
            mis_control_plane_dependency(
                action="mis_snapshot_view", resource_type="mis_template_version"
            )
        )
    ],
)
async def list_template_versions(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[TemplateVersionSummaryResponse]:
    service = _build_service(session)
    versions = await service.list_template_versions(
        tenant_id=user.tenant_id, template_id=id
    )
    return [
        TemplateVersionSummaryResponse(
            id=row.id,
            version_no=row.version_no,
            version_token=row.version_token,
            status=row.status,
            structure_hash=row.structure_hash,
            created_at=row.created_at.isoformat(),
        )
        for row in versions
    ]


@router.get(
    "/snapshots/{id}",
    dependencies=[
        Depends(
            mis_control_plane_dependency(
                action="mis_snapshot_view", resource_type="mis_snapshot"
            )
        )
    ],
)
async def get_snapshot(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    service = _build_service(session)
    row = await service.get_snapshot(tenant_id=user.tenant_id, snapshot_id=id)
    if row is None:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return {
        "id": str(row.id),
        "template_id": str(row.template_id),
        "template_version_id": str(row.template_version_id),
        "reporting_period": row.reporting_period.isoformat(),
        "snapshot_token": row.snapshot_token,
        "snapshot_status": row.snapshot_status,
        "validation_summary_json": row.validation_summary_json,
        "created_at": row.created_at.isoformat(),
    }


@router.get(
    "/snapshots/{id}/exceptions",
    dependencies=[
        Depends(
            mis_control_plane_dependency(
                action="mis_snapshot_view", resource_type="mis_ingestion_exception"
            )
        )
    ],
)
async def get_snapshot_exceptions(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    service = _build_service(session)
    rows = await service.list_snapshot_exceptions(
        tenant_id=user.tenant_id, snapshot_id=id
    )
    return [
        {
            "id": str(row.id),
            "exception_code": row.exception_code,
            "severity": row.severity,
            "source_ref": row.source_ref,
            "message": row.message,
            "resolution_status": row.resolution_status,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]


@router.get(
    "/drift-events/{id}",
    dependencies=[
        Depends(
            mis_control_plane_dependency(
                action="mis_template_review", resource_type="mis_drift_event"
            )
        )
    ],
)
async def get_drift_event(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    service = _build_service(session)
    row = await service.get_drift_event(tenant_id=user.tenant_id, drift_event_id=id)
    if row is None:
        raise HTTPException(status_code=404, detail="Drift event not found")
    return {
        "id": str(row.id),
        "template_id": str(row.template_id),
        "prior_template_version_id": str(row.prior_template_version_id),
        "candidate_template_version_id": str(row.candidate_template_version_id),
        "drift_type": row.drift_type,
        "drift_details_json": row.drift_details_json,
        "decision_status": row.decision_status,
        "created_at": row.created_at.isoformat(),
    }


@router.get(
    "/snapshots/{id}/normalized-lines",
    dependencies=[
        Depends(
            mis_control_plane_dependency(
                action="mis_snapshot_view", resource_type="mis_normalized_line"
            )
        )
    ],
)
async def get_normalized_lines(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    service = _build_service(session)
    rows = await service.list_normalized_lines(tenant_id=user.tenant_id, snapshot_id=id)
    return [
        {
            "id": str(row.id),
            "line_no": row.line_no,
            "canonical_metric_code": row.canonical_metric_code,
            "canonical_dimension_json": row.canonical_dimension_json,
            "source_row_ref": row.source_row_ref,
            "source_column_ref": row.source_column_ref,
            "period_value": str(row.period_value),
            "currency_code": row.currency_code,
            "sign_applied": row.sign_applied,
            "validation_status": row.validation_status,
        }
        for row in rows
    ]


@router.get(
    "/snapshots/{id}/summary",
    dependencies=[
        Depends(
            mis_control_plane_dependency(
                action="mis_snapshot_view", resource_type="mis_snapshot"
            )
        )
    ],
)
async def get_snapshot_summary(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    service = _build_service(session)
    return await service.snapshot_summary(tenant_id=user.tenant_id, snapshot_id=id)
