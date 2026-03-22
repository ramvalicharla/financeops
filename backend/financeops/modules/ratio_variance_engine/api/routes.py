from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user
from financeops.db.models.users import IamUser
from financeops.modules.ratio_variance_engine.api.schemas import (
    MaterialityRuleCreateRequest,
    MetricDefinitionCreateRequest,
    RunCreateRequest,
    RunCreateResponse,
    RunExecuteResponse,
    RunSummaryResponse,
    TrendDefinitionCreateRequest,
    VarianceDefinitionCreateRequest,
)
from financeops.modules.ratio_variance_engine.application.materiality_service import (
    MaterialityService,
)
from financeops.modules.ratio_variance_engine.application.metric_definition_service import (
    MetricDefinitionService,
)
from financeops.modules.ratio_variance_engine.application.run_service import RunService
from financeops.modules.ratio_variance_engine.application.trend_service import TrendService
from financeops.modules.ratio_variance_engine.application.validation_service import (
    ValidationService,
)
from financeops.modules.ratio_variance_engine.application.variance_service import (
    VarianceService,
)
from financeops.modules.ratio_variance_engine.domain.value_objects import (
    DefinitionVersionTokenInput,
)
from financeops.modules.ratio_variance_engine.infrastructure.repository import (
    RatioVarianceRepository,
)
from financeops.modules.ratio_variance_engine.infrastructure.token_builder import (
    build_definition_version_token,
)
from financeops.modules.ratio_variance_engine.policies.control_plane_policy import (
    ratio_variance_control_plane_dependency,
)

router = APIRouter()


def _build_run_service(session: AsyncSession) -> RunService:
    return RunService(
        repository=RatioVarianceRepository(session),
        metric_definition_service=MetricDefinitionService(),
        variance_service=VarianceService(),
        trend_service=TrendService(),
        materiality_service=MaterialityService(),
        validation_service=ValidationService(),
    )


@router.post(
    "/metric-definitions",
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(
            ratio_variance_control_plane_dependency(
                action="metric_definition_manage",
                resource_type="metric_definition",
            )
        )
    ],
)
async def create_metric_definition(
    body: MetricDefinitionCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    repository = RatioVarianceRepository(session)
    version_token = build_definition_version_token(
        DefinitionVersionTokenInput(
            rows=[
                {
                    "definition_code": body.definition_code,
                    "definition_name": body.definition_name,
                    "metric_code": body.metric_code,
                    "formula_type": body.formula_type,
                    "formula_json": body.formula_json,
                    "unit_type": body.unit_type,
                    "directionality": body.directionality,
                    "effective_from": body.effective_from.isoformat(),
                    "status": body.status,
                    "components": [
                        {
                            "component_code": item.component_code,
                            "source_type": item.source_type,
                            "source_key": item.source_key,
                            "operator": item.operator,
                            "weight": str(item.weight),
                            "ordinal_position": item.ordinal_position,
                            "metadata_json": item.metadata_json,
                        }
                        for item in sorted(body.components, key=lambda row: row.ordinal_position)
                    ],
                }
            ]
        )
    )
    try:
        row = await repository.create_metric_definition(
            tenant_id=user.tenant_id,
            organisation_id=body.organisation_id,
            definition_code=body.definition_code,
            definition_name=body.definition_name,
            metric_code=body.metric_code,
            formula_type=body.formula_type,
            formula_json=body.formula_json,
            unit_type=body.unit_type,
            directionality=body.directionality,
            version_token=version_token,
            effective_from=body.effective_from,
            supersedes_id=body.supersedes_id,
            status=body.status,
            components=[item.model_dump() for item in body.components],
            created_by=user.id,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail="internal_error") from exc
    await session.flush()
    return {
        "id": str(row.id),
        "definition_code": row.definition_code,
        "version_token": row.version_token,
        "status": row.status,
    }


@router.get(
    "/metric-definitions",
    dependencies=[
        Depends(
            ratio_variance_control_plane_dependency(
                action="ratio_variance_view",
                resource_type="metric_definition",
            )
        )
    ],
)
async def list_metric_definitions(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    repository = RatioVarianceRepository(session)
    rows = await repository.list_metric_definitions(tenant_id=user.tenant_id)
    return [
        {
            "id": str(row.id),
            "definition_code": row.definition_code,
            "definition_name": row.definition_name,
            "metric_code": row.metric_code,
            "formula_type": row.formula_type,
            "unit_type": row.unit_type,
            "directionality": row.directionality,
            "version_token": row.version_token,
            "status": row.status,
            "effective_from": row.effective_from.isoformat(),
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]


@router.get(
    "/metric-definitions/{id}/versions",
    dependencies=[
        Depends(
            ratio_variance_control_plane_dependency(
                action="ratio_variance_view",
                resource_type="metric_definition",
            )
        )
    ],
)
async def list_metric_definition_versions(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    repository = RatioVarianceRepository(session)
    rows = await repository.list_metric_definition_versions(
        tenant_id=user.tenant_id,
        definition_id=id,
    )
    return [
        {
            "id": str(row.id),
            "definition_code": row.definition_code,
            "definition_name": row.definition_name,
            "metric_code": row.metric_code,
            "version_token": row.version_token,
            "status": row.status,
            "effective_from": row.effective_from.isoformat(),
        }
        for row in rows
    ]


@router.post(
    "/variance-definitions",
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(
            ratio_variance_control_plane_dependency(
                action="variance_definition_manage",
                resource_type="variance_definition",
            )
        )
    ],
)
async def create_variance_definition(
    body: VarianceDefinitionCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    repository = RatioVarianceRepository(session)
    version_token = build_definition_version_token(
        DefinitionVersionTokenInput(
            rows=[
                {
                    "definition_code": body.definition_code,
                    "definition_name": body.definition_name,
                    "metric_code": body.metric_code,
                    "comparison_type": body.comparison_type,
                    "configuration_json": body.configuration_json,
                    "effective_from": body.effective_from.isoformat(),
                    "status": body.status,
                }
            ]
        )
    )
    try:
        row = await repository.create_variance_definition(
            tenant_id=user.tenant_id,
            organisation_id=body.organisation_id,
            definition_code=body.definition_code,
            definition_name=body.definition_name,
            metric_code=body.metric_code,
            comparison_type=body.comparison_type,
            configuration_json=body.configuration_json,
            version_token=version_token,
            effective_from=body.effective_from,
            supersedes_id=body.supersedes_id,
            status=body.status,
            created_by=user.id,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail="internal_error") from exc
    await session.flush()
    return {
        "id": str(row.id),
        "definition_code": row.definition_code,
        "version_token": row.version_token,
        "status": row.status,
    }


@router.get(
    "/variance-definitions",
    dependencies=[
        Depends(
            ratio_variance_control_plane_dependency(
                action="ratio_variance_view",
                resource_type="variance_definition",
            )
        )
    ],
)
async def list_variance_definitions(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    repository = RatioVarianceRepository(session)
    rows = await repository.list_variance_definitions(tenant_id=user.tenant_id)
    return [
        {
            "id": str(row.id),
            "definition_code": row.definition_code,
            "definition_name": row.definition_name,
            "metric_code": row.metric_code,
            "comparison_type": row.comparison_type,
            "version_token": row.version_token,
            "status": row.status,
            "effective_from": row.effective_from.isoformat(),
        }
        for row in rows
    ]


@router.get(
    "/variance-definitions/{id}/versions",
    dependencies=[
        Depends(
            ratio_variance_control_plane_dependency(
                action="ratio_variance_view",
                resource_type="variance_definition",
            )
        )
    ],
)
async def list_variance_definition_versions(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    repository = RatioVarianceRepository(session)
    rows = await repository.list_variance_definition_versions(
        tenant_id=user.tenant_id,
        definition_id=id,
    )
    return [
        {
            "id": str(row.id),
            "definition_code": row.definition_code,
            "definition_name": row.definition_name,
            "metric_code": row.metric_code,
            "comparison_type": row.comparison_type,
            "version_token": row.version_token,
            "status": row.status,
            "effective_from": row.effective_from.isoformat(),
        }
        for row in rows
    ]


@router.post(
    "/trend-definitions",
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(
            ratio_variance_control_plane_dependency(
                action="trend_definition_manage",
                resource_type="trend_definition",
            )
        )
    ],
)
async def create_trend_definition(
    body: TrendDefinitionCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    repository = RatioVarianceRepository(session)
    version_token = build_definition_version_token(
        DefinitionVersionTokenInput(
            rows=[
                {
                    "definition_code": body.definition_code,
                    "definition_name": body.definition_name,
                    "metric_code": body.metric_code,
                    "trend_type": body.trend_type,
                    "window_size": body.window_size,
                    "configuration_json": body.configuration_json,
                    "effective_from": body.effective_from.isoformat(),
                    "status": body.status,
                }
            ]
        )
    )
    try:
        row = await repository.create_trend_definition(
            tenant_id=user.tenant_id,
            organisation_id=body.organisation_id,
            definition_code=body.definition_code,
            definition_name=body.definition_name,
            metric_code=body.metric_code,
            trend_type=body.trend_type,
            window_size=body.window_size,
            configuration_json=body.configuration_json,
            version_token=version_token,
            effective_from=body.effective_from,
            supersedes_id=body.supersedes_id,
            status=body.status,
            created_by=user.id,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail="internal_error") from exc
    await session.flush()
    return {
        "id": str(row.id),
        "definition_code": row.definition_code,
        "version_token": row.version_token,
        "status": row.status,
    }


@router.get(
    "/trend-definitions",
    dependencies=[
        Depends(
            ratio_variance_control_plane_dependency(
                action="ratio_variance_view",
                resource_type="trend_definition",
            )
        )
    ],
)
async def list_trend_definitions(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    repository = RatioVarianceRepository(session)
    rows = await repository.list_trend_definitions(tenant_id=user.tenant_id)
    return [
        {
            "id": str(row.id),
            "definition_code": row.definition_code,
            "definition_name": row.definition_name,
            "metric_code": row.metric_code,
            "trend_type": row.trend_type,
            "window_size": row.window_size,
            "version_token": row.version_token,
            "status": row.status,
            "effective_from": row.effective_from.isoformat(),
        }
        for row in rows
    ]


@router.get(
    "/trend-definitions/{id}/versions",
    dependencies=[
        Depends(
            ratio_variance_control_plane_dependency(
                action="ratio_variance_view",
                resource_type="trend_definition",
            )
        )
    ],
)
async def list_trend_definition_versions(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    repository = RatioVarianceRepository(session)
    rows = await repository.list_trend_definition_versions(
        tenant_id=user.tenant_id,
        definition_id=id,
    )
    return [
        {
            "id": str(row.id),
            "definition_code": row.definition_code,
            "definition_name": row.definition_name,
            "metric_code": row.metric_code,
            "trend_type": row.trend_type,
            "window_size": row.window_size,
            "version_token": row.version_token,
            "status": row.status,
            "effective_from": row.effective_from.isoformat(),
        }
        for row in rows
    ]


@router.post(
    "/materiality-rules",
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(
            ratio_variance_control_plane_dependency(
                action="materiality_rule_manage",
                resource_type="materiality_rule",
            )
        )
    ],
)
async def create_materiality_rule(
    body: MaterialityRuleCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    repository = RatioVarianceRepository(session)
    version_token = build_definition_version_token(
        DefinitionVersionTokenInput(
            rows=[
                {
                    "definition_code": body.definition_code,
                    "definition_name": body.definition_name,
                    "rule_json": body.rule_json,
                    "effective_from": body.effective_from.isoformat(),
                    "status": body.status,
                }
            ]
        )
    )
    try:
        row = await repository.create_materiality_rule(
            tenant_id=user.tenant_id,
            organisation_id=body.organisation_id,
            definition_code=body.definition_code,
            definition_name=body.definition_name,
            rule_json=body.rule_json,
            version_token=version_token,
            effective_from=body.effective_from,
            supersedes_id=body.supersedes_id,
            status=body.status,
            created_by=user.id,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail="internal_error") from exc
    await session.flush()
    return {
        "id": str(row.id),
        "definition_code": row.definition_code,
        "version_token": row.version_token,
        "status": row.status,
    }


@router.get(
    "/materiality-rules",
    dependencies=[
        Depends(
            ratio_variance_control_plane_dependency(
                action="ratio_variance_view",
                resource_type="materiality_rule",
            )
        )
    ],
)
async def list_materiality_rules(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    repository = RatioVarianceRepository(session)
    rows = await repository.list_materiality_rules(tenant_id=user.tenant_id)
    return [
        {
            "id": str(row.id),
            "definition_code": row.definition_code,
            "definition_name": row.definition_name,
            "version_token": row.version_token,
            "status": row.status,
            "effective_from": row.effective_from.isoformat(),
        }
        for row in rows
    ]


@router.get(
    "/materiality-rules/{id}/versions",
    dependencies=[
        Depends(
            ratio_variance_control_plane_dependency(
                action="ratio_variance_view",
                resource_type="materiality_rule",
            )
        )
    ],
)
async def list_materiality_rule_versions(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    repository = RatioVarianceRepository(session)
    rows = await repository.list_materiality_rule_versions(
        tenant_id=user.tenant_id,
        definition_id=id,
    )
    return [
        {
            "id": str(row.id),
            "definition_code": row.definition_code,
            "definition_name": row.definition_name,
            "version_token": row.version_token,
            "status": row.status,
            "effective_from": row.effective_from.isoformat(),
        }
        for row in rows
    ]


@router.post(
    "/runs",
    response_model=RunCreateResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(
            ratio_variance_control_plane_dependency(
                action="ratio_variance_run",
                resource_type="metric_run",
            )
        )
    ],
)
async def create_run(
    body: RunCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> RunCreateResponse:
    service = _build_run_service(session)
    try:
        result = await service.create_run(
            tenant_id=user.tenant_id,
            organisation_id=body.organisation_id,
            reporting_period=body.reporting_period,
            scope_json=body.scope_json,
            mis_snapshot_id=body.mis_snapshot_id,
            payroll_run_id=body.payroll_run_id,
            gl_run_id=body.gl_run_id,
            reconciliation_session_id=body.reconciliation_session_id,
            payroll_gl_reconciliation_run_id=body.payroll_gl_reconciliation_run_id,
            created_by=user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="internal_error") from exc
    await session.flush()
    return RunCreateResponse(**result)


@router.post(
    "/runs/{id}/execute",
    response_model=RunExecuteResponse,
    dependencies=[
        Depends(
            ratio_variance_control_plane_dependency(
                action="ratio_variance_run",
                resource_type="metric_run",
            )
        )
    ],
)
async def execute_run(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> RunExecuteResponse:
    service = _build_run_service(session)
    try:
        result = await service.execute_run(
            tenant_id=user.tenant_id,
            run_id=id,
            actor_user_id=user.id,
        )
    except ValueError as exc:
        detail = str(exc)
        raise HTTPException(
            status_code=404 if "not found" in detail.lower() else 400,
            detail=detail,
        ) from exc
    await session.flush()
    return RunExecuteResponse(**result)


@router.get(
    "/runs/{id}",
    dependencies=[
        Depends(
            ratio_variance_control_plane_dependency(
                action="ratio_variance_view",
                resource_type="metric_run",
            )
        )
    ],
)
async def get_run(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    service = _build_run_service(session)
    row = await service.get_run(tenant_id=user.tenant_id, run_id=id)
    if row is None:
        raise HTTPException(status_code=404, detail="Ratio/Variance run not found")
    return row


@router.get(
    "/runs/{id}/summary",
    response_model=RunSummaryResponse,
    dependencies=[
        Depends(
            ratio_variance_control_plane_dependency(
                action="ratio_variance_view",
                resource_type="metric_run",
            )
        )
    ],
)
async def get_summary(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> RunSummaryResponse:
    service = _build_run_service(session)
    try:
        result = await service.summary(tenant_id=user.tenant_id, run_id=id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="internal_error") from exc
    return RunSummaryResponse(**result)


@router.get(
    "/runs/{id}/metrics",
    dependencies=[
        Depends(
            ratio_variance_control_plane_dependency(
                action="ratio_variance_view",
                resource_type="metric_run",
            )
        )
    ],
)
async def list_metrics(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    service = _build_run_service(session)
    return await service.list_metrics(tenant_id=user.tenant_id, run_id=id)


@router.get(
    "/runs/{id}/variances",
    dependencies=[
        Depends(
            ratio_variance_control_plane_dependency(
                action="ratio_variance_view",
                resource_type="metric_run",
            )
        )
    ],
)
async def list_variances(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    service = _build_run_service(session)
    return await service.list_variances(tenant_id=user.tenant_id, run_id=id)


@router.get(
    "/runs/{id}/trends",
    dependencies=[
        Depends(
            ratio_variance_control_plane_dependency(
                action="ratio_variance_view",
                resource_type="metric_run",
            )
        )
    ],
)
async def list_trends(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    service = _build_run_service(session)
    return await service.list_trends(tenant_id=user.tenant_id, run_id=id)


@router.get(
    "/runs/{id}/evidence",
    dependencies=[
        Depends(
            ratio_variance_control_plane_dependency(
                action="ratio_variance_evidence_view",
                resource_type="metric_evidence_link",
            )
        )
    ],
)
async def list_evidence(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    service = _build_run_service(session)
    return await service.list_evidence(tenant_id=user.tenant_id, run_id=id)
