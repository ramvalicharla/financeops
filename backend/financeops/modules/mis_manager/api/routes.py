from __future__ import annotations

import uuid
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user
from financeops.db.models.tenants import IamTenant
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
from financeops.modules.mis_manager.application.report_service import (
    apply_scale_to_mis_report,
    get_mis_report_by_id,
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
from financeops.shared_kernel.pagination import Paginated
from financeops.utils.display_scale import DisplayScale, get_effective_scale

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


_DASHBOARD_METRIC_MAP: dict[str, str] = {
    "revenue": "revenue",
    "revenue_net": "revenue",
    "gross_profit": "gross_profit",
    "ebitda": "ebitda",
    "net_profit": "net_profit",
    "profit_after_tax": "net_profit",
    "pat": "net_profit",
}


def _parse_period(period: str) -> date:
    """Accept YYYY-MM or YYYY-MM-DD, return the corresponding date."""
    clean = period.strip()
    if len(clean) == 7:  # YYYY-MM — treat as first day of month
        return date.fromisoformat(clean + "-01")
    return date.fromisoformat(clean)


def _prev_period(d: date) -> date:
    if d.month == 1:
        return date(d.year - 1, 12, 1)
    return date(d.year, d.month - 1, 1)


def _period_label(d: date) -> str:
    return d.strftime("%b %Y")


def _aggregate_metrics(lines: list) -> dict[str, Decimal]:
    totals: dict[str, Decimal] = {
        "revenue": Decimal("0"),
        "gross_profit": Decimal("0"),
        "ebitda": Decimal("0"),
        "net_profit": Decimal("0"),
    }
    for line in lines:
        metric = (line.canonical_metric_code or "").strip().lower()
        target = _DASHBOARD_METRIC_MAP.get(metric)
        if target is not None:
            totals[target] += Decimal(str(line.period_value))
    return totals


def _pct_change(current: Decimal, previous: Decimal) -> str:
    if previous == Decimal("0"):
        return "0"
    return str(
        ((current - previous) / abs(previous) * 100).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
    )


def _build_empty_dashboard(entity_id: str, period: str) -> dict:
    return {
        "entity_id": entity_id,
        "period": period,
        "previous_period": "",
        "revenue": "0",
        "gross_profit": "0",
        "ebitda": "0",
        "net_profit": "0",
        "revenue_change_pct": "0",
        "gross_profit_change_pct": "0",
        "ebitda_change_pct": "0",
        "net_profit_change_pct": "0",
        "line_items": [],
        "chart_data": [],
    }


@router.get("/dashboard")
async def get_mis_dashboard(
    period: str = Query(..., description="Reporting period: YYYY-MM or YYYY-MM-DD"),
    entity_id: uuid.UUID | None = Query(default=None),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    try:
        period_date = _parse_period(period)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid period format: {period!r}")

    entity_id_str = str(entity_id) if entity_id is not None else ""
    repo = MisManagerRepository(session)

    snapshot = await repo.get_latest_snapshot_for_period(
        tenant_id=user.tenant_id,
        entity_id=entity_id,
        reporting_period=period_date,
    )
    if snapshot is None:
        return _build_empty_dashboard(entity_id_str, period_date.isoformat())

    lines = await repo.list_normalized_lines(
        tenant_id=user.tenant_id, snapshot_id=snapshot.id
    )
    curr = _aggregate_metrics(lines)

    prev_date = _prev_period(period_date)
    prev_snapshot = await repo.get_latest_snapshot_for_period(
        tenant_id=user.tenant_id,
        entity_id=entity_id,
        reporting_period=prev_date,
    )
    prev: dict[str, Decimal] = {k: Decimal("0") for k in curr}
    if prev_snapshot is not None:
        prev_lines = await repo.list_normalized_lines(
            tenant_id=user.tenant_id, snapshot_id=prev_snapshot.id
        )
        prev = _aggregate_metrics(prev_lines)

    line_items = [
        {
            "line_item_id": str(line.id),
            "label": line.canonical_metric_code,
            "current_value": str(line.period_value),
            "previous_value": "0",
            "variance": str(line.period_value),
            "variance_pct": "0",
            "is_heading": False,
            "indent_level": 0,
        }
        for line in lines
    ]

    return {
        "entity_id": str(snapshot.entity_id) if snapshot.entity_id else entity_id_str,
        "period": period_date.isoformat(),
        "previous_period": prev_date.isoformat(),
        "revenue": str(curr["revenue"]),
        "gross_profit": str(curr["gross_profit"]),
        "ebitda": str(curr["ebitda"]),
        "net_profit": str(curr["net_profit"]),
        "revenue_change_pct": _pct_change(curr["revenue"], prev["revenue"]),
        "gross_profit_change_pct": _pct_change(curr["gross_profit"], prev["gross_profit"]),
        "ebitda_change_pct": _pct_change(curr["ebitda"], prev["ebitda"]),
        "net_profit_change_pct": _pct_change(curr["net_profit"], prev["net_profit"]),
        "line_items": line_items,
        "chart_data": [
            {
                "period": period_date.isoformat(),
                "label": _period_label(period_date),
                "revenue": str(curr["revenue"]),
                "gross_profit": str(curr["gross_profit"]),
                "ebitda": str(curr["ebitda"]),
            }
        ],
    }


@router.get("/periods")
async def get_mis_periods(
    entity_id: uuid.UUID | None = Query(default=None),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    repo = MisManagerRepository(session)
    snapshots = await repo.list_snapshots_for_entity(
        tenant_id=user.tenant_id,
        entity_id=entity_id,
    )
    seen: set[date] = set()
    result: list[dict] = []
    for snap in snapshots:
        p = snap.reporting_period
        if p not in seen:
            seen.add(p)
            result.append({"period": p.isoformat(), "label": _period_label(p)})
    return result


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
        raise HTTPException(status_code=400, detail="internal_error") from exc
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
        raise HTTPException(status_code=400, detail="internal_error") from exc
    await session.flush()
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
        raise HTTPException(status_code=400, detail="internal_error") from exc
    await session.flush()
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
    await session.flush()
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
    await session.flush()
    return SnapshotStatusActionResponse(**result)


@router.get(
    "/templates",
    response_model=Paginated[TemplateSummaryResponse] | list[TemplateSummaryResponse],
    dependencies=[
        Depends(
            mis_control_plane_dependency(
                action="mis_snapshot_view", resource_type="mis_template"
            )
        )
    ],
)
async def list_templates(
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> Paginated[TemplateSummaryResponse] | list[TemplateSummaryResponse]:
    service = _build_service(session)
    templates = await service.list_templates(tenant_id=user.tenant_id)
    data = [
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
    if "limit" not in request.query_params and "offset" not in request.query_params:
        return data
    return Paginated[TemplateSummaryResponse](
        data=data[offset : offset + limit],
        total=len(data),
        limit=limit,
        offset=offset,
    )


@router.get(
    "/reports/{report_id}",
    dependencies=[
        Depends(
            mis_control_plane_dependency(
                action="mis_snapshot_view", resource_type="mis_snapshot"
            )
        )
    ],
)
async def get_mis_report(
    report_id: uuid.UUID,
    display_scale: str | None = Query(
        default=None,
        description="Override display scale: INR|LAKHS|CRORES|THOUSANDS|MILLIONS|BILLIONS",
    ),
    session: AsyncSession = Depends(get_async_session),
    current_user: IamUser = Depends(get_current_user),
) -> dict:
    report = await get_mis_report_by_id(
        session=session,
        report_id=report_id,
        tenant_id=current_user.tenant_id,
    )
    if report is None:
        raise HTTPException(status_code=404, detail="MIS report not found")

    tenant = await session.get(IamTenant, current_user.tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")

    user_scale = display_scale or current_user.display_scale_override
    scale = get_effective_scale(user_scale, tenant.default_display_scale)
    try:
        scale = DisplayScale(scale.value)
    except ValueError:
        scale = DisplayScale.LAKHS
    return apply_scale_to_mis_report(report, scale)


@router.get(
    "/templates/{id}/versions",
    response_model=Paginated[TemplateVersionSummaryResponse] | list[TemplateVersionSummaryResponse],
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
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> Paginated[TemplateVersionSummaryResponse] | list[TemplateVersionSummaryResponse]:
    service = _build_service(session)
    versions = await service.list_template_versions(
        tenant_id=user.tenant_id, template_id=id
    )
    data = [
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
    if "limit" not in request.query_params and "offset" not in request.query_params:
        return data
    return Paginated[TemplateVersionSummaryResponse](
        data=data[offset : offset + limit],
        total=len(data),
        limit=limit,
        offset=offset,
    )


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
