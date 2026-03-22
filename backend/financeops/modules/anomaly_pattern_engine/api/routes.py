from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user
from financeops.db.models.users import IamUser
from financeops.modules.anomaly_pattern_engine.api.schemas import (
    AnomalyCorrelationRuleCreateRequest,
    AnomalyDefinitionCreateRequest,
    AnomalyPatternRuleCreateRequest,
    AnomalyPersistenceRuleCreateRequest,
    AnomalyRunCreateRequest,
    AnomalyRunCreateResponse,
    AnomalyRunExecuteResponse,
    AnomalyStatisticalRuleCreateRequest,
)
from financeops.modules.anomaly_pattern_engine.application.correlation_service import (
    CorrelationService,
)
from financeops.modules.anomaly_pattern_engine.application.materiality_service import (
    MaterialityService,
)
from financeops.modules.anomaly_pattern_engine.application.persistence_service import (
    PersistenceService,
)
from financeops.modules.anomaly_pattern_engine.application.run_service import RunService
from financeops.modules.anomaly_pattern_engine.application.scoring_service import ScoringService
from financeops.modules.anomaly_pattern_engine.application.statistical_service import (
    StatisticalService,
)
from financeops.modules.anomaly_pattern_engine.application.validation_service import (
    ValidationService,
)
from financeops.modules.anomaly_pattern_engine.domain.value_objects import (
    DefinitionVersionTokenInput,
)
from financeops.modules.anomaly_pattern_engine.infrastructure.repository import (
    AnomalyPatternRepository,
)
from financeops.modules.anomaly_pattern_engine.infrastructure.token_builder import (
    build_definition_version_token,
)
from financeops.modules.anomaly_pattern_engine.policies.control_plane_policy import (
    anomaly_engine_control_plane_dependency,
)

router = APIRouter()


def _build_service(session: AsyncSession) -> RunService:
    return RunService(
        repository=AnomalyPatternRepository(session),
        validation_service=ValidationService(),
        statistical_service=StatisticalService(),
        scoring_service=ScoringService(),
        materiality_service=MaterialityService(),
        persistence_service=PersistenceService(),
        correlation_service=CorrelationService(),
    )


@router.post(
    "/anomaly-definitions",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(anomaly_engine_control_plane_dependency(action="anomaly_definition_manage", resource_type="anomaly_definition"))],
)
async def create_anomaly_definition(
    body: AnomalyDefinitionCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    repository = AnomalyPatternRepository(session)
    version_token = build_definition_version_token(
        DefinitionVersionTokenInput(
            rows=[
                {
                    "anomaly_code": body.anomaly_code,
                    "anomaly_name": body.anomaly_name,
                    "anomaly_domain": body.anomaly_domain,
                    "signal_selector_json": body.signal_selector_json,
                    "definition_json": body.definition_json,
                    "effective_from": body.effective_from.isoformat(),
                    "effective_to": body.effective_to.isoformat() if body.effective_to else None,
                    "status": body.status,
                }
            ]
        )
    )
    try:
        row = await repository.create_anomaly_definition(
            tenant_id=user.tenant_id,
            organisation_id=body.organisation_id,
            anomaly_code=body.anomaly_code,
            anomaly_name=body.anomaly_name,
            anomaly_domain=body.anomaly_domain,
            signal_selector_json=body.signal_selector_json,
            definition_json=body.definition_json,
            version_token=version_token,
            effective_from=body.effective_from,
            effective_to=body.effective_to,
            supersedes_id=body.supersedes_id,
            status=body.status,
            created_by=user.id,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail="internal_error") from exc
    await session.flush()
    return {"id": str(row.id), "anomaly_code": row.anomaly_code, "version_token": row.version_token, "status": row.status}


@router.get(
    "/anomaly-definitions",
    dependencies=[Depends(anomaly_engine_control_plane_dependency(action="anomaly_engine_view", resource_type="anomaly_definition"))],
)
async def list_anomaly_definitions(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    rows = await AnomalyPatternRepository(session).list_anomaly_definitions(tenant_id=user.tenant_id)
    return [{"id": str(r.id), "anomaly_code": r.anomaly_code, "anomaly_name": r.anomaly_name, "anomaly_domain": r.anomaly_domain, "version_token": r.version_token, "status": r.status, "effective_from": r.effective_from.isoformat()} for r in rows]


@router.get(
    "/anomaly-definitions/{id}/versions",
    dependencies=[Depends(anomaly_engine_control_plane_dependency(action="anomaly_engine_view", resource_type="anomaly_definition"))],
)
async def list_anomaly_definition_versions(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    rows = await AnomalyPatternRepository(session).list_anomaly_definition_versions(
        tenant_id=user.tenant_id, definition_id=id
    )
    return [{"id": str(r.id), "anomaly_code": r.anomaly_code, "version_token": r.version_token, "status": r.status, "effective_from": r.effective_from.isoformat()} for r in rows]


async def _create_rule(
    *,
    request_body: dict,
    session: AsyncSession,
    user: IamUser,
    create_fn: str,
) -> dict:
    repository = AnomalyPatternRepository(session)
    version_token = build_definition_version_token(DefinitionVersionTokenInput(rows=[request_body]))
    payload = dict(request_body)
    payload.pop("organisation_id", None)
    payload["version_token"] = version_token
    payload["created_by"] = user.id
    payload["tenant_id"] = user.tenant_id
    payload["organisation_id"] = request_body["organisation_id"]
    try:
        row = await getattr(repository, create_fn)(**payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="internal_error") from exc
    await session.flush()
    return {"id": str(row.id), "rule_code": row.rule_code, "version_token": row.version_token, "status": row.status}


@router.post(
    "/pattern-rules",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(anomaly_engine_control_plane_dependency(action="anomaly_pattern_rule_manage", resource_type="anomaly_pattern_rule"))],
)
async def create_pattern_rule(
    body: AnomalyPatternRuleCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    return await _create_rule(
        request_body=body.model_dump(),
        session=session,
        user=user,
        create_fn="create_pattern_rule",
    )


@router.get(
    "/pattern-rules",
    dependencies=[Depends(anomaly_engine_control_plane_dependency(action="anomaly_engine_view", resource_type="anomaly_pattern_rule"))],
)
async def list_pattern_rules(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    rows = await AnomalyPatternRepository(session).list_pattern_rules(tenant_id=user.tenant_id)
    return [{"id": str(r.id), "rule_code": r.rule_code, "rule_name": r.rule_name, "version_token": r.version_token, "status": r.status} for r in rows]


@router.post(
    "/persistence-rules",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(anomaly_engine_control_plane_dependency(action="anomaly_persistence_rule_manage", resource_type="anomaly_persistence_rule"))],
)
async def create_persistence_rule(
    body: AnomalyPersistenceRuleCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    return await _create_rule(
        request_body=body.model_dump(),
        session=session,
        user=user,
        create_fn="create_persistence_rule",
    )


@router.get(
    "/persistence-rules",
    dependencies=[Depends(anomaly_engine_control_plane_dependency(action="anomaly_engine_view", resource_type="anomaly_persistence_rule"))],
)
async def list_persistence_rules(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    rows = await AnomalyPatternRepository(session).list_persistence_rules(tenant_id=user.tenant_id)
    return [{"id": str(r.id), "rule_code": r.rule_code, "rule_name": r.rule_name, "version_token": r.version_token, "status": r.status} for r in rows]


@router.post(
    "/correlation-rules",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(anomaly_engine_control_plane_dependency(action="anomaly_correlation_rule_manage", resource_type="anomaly_correlation_rule"))],
)
async def create_correlation_rule(
    body: AnomalyCorrelationRuleCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    return await _create_rule(
        request_body=body.model_dump(),
        session=session,
        user=user,
        create_fn="create_correlation_rule",
    )


@router.get(
    "/correlation-rules",
    dependencies=[Depends(anomaly_engine_control_plane_dependency(action="anomaly_engine_view", resource_type="anomaly_correlation_rule"))],
)
async def list_correlation_rules(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    rows = await AnomalyPatternRepository(session).list_correlation_rules(tenant_id=user.tenant_id)
    return [{"id": str(r.id), "rule_code": r.rule_code, "rule_name": r.rule_name, "version_token": r.version_token, "status": r.status} for r in rows]


@router.post(
    "/statistical-rules",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(anomaly_engine_control_plane_dependency(action="anomaly_statistical_rule_manage", resource_type="anomaly_statistical_rule"))],
)
async def create_statistical_rule(
    body: AnomalyStatisticalRuleCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    return await _create_rule(
        request_body=body.model_dump(),
        session=session,
        user=user,
        create_fn="create_statistical_rule",
    )


@router.get(
    "/statistical-rules",
    dependencies=[Depends(anomaly_engine_control_plane_dependency(action="anomaly_engine_view", resource_type="anomaly_statistical_rule"))],
)
async def list_statistical_rules(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    rows = await AnomalyPatternRepository(session).list_statistical_rules(tenant_id=user.tenant_id)
    return [{"id": str(r.id), "rule_code": r.rule_code, "rule_name": r.rule_name, "version_token": r.version_token, "status": r.status} for r in rows]


@router.post(
    "/runs",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(anomaly_engine_control_plane_dependency(action="anomaly_engine_run", resource_type="anomaly_run"))],
    response_model=AnomalyRunCreateResponse,
)
async def create_run(
    body: AnomalyRunCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    try:
        payload = await _build_service(session).create_run(
            tenant_id=user.tenant_id,
            organisation_id=body.organisation_id,
            reporting_period=body.reporting_period,
            source_metric_run_ids=body.source_metric_run_ids,
            source_variance_run_ids=body.source_variance_run_ids,
            source_trend_run_ids=body.source_trend_run_ids,
            source_risk_run_ids=body.source_risk_run_ids,
            source_reconciliation_session_ids=body.source_reconciliation_session_ids,
            created_by=user.id,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail="internal_error") from exc
    await session.flush()
    return payload


@router.post(
    "/runs/{id}/execute",
    dependencies=[Depends(anomaly_engine_control_plane_dependency(action="anomaly_engine_run", resource_type="anomaly_run"))],
    response_model=AnomalyRunExecuteResponse,
)
async def execute_run(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    try:
        payload = await _build_service(session).execute_run(
            tenant_id=user.tenant_id, run_id=id, actor_user_id=user.id
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="internal_error") from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail="internal_error") from exc
    await session.flush()
    return payload


@router.get("/runs/{id}", dependencies=[Depends(anomaly_engine_control_plane_dependency(action="anomaly_engine_view", resource_type="anomaly_run"))])
async def get_run(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    row = await _build_service(session).get_run(tenant_id=user.tenant_id, run_id=id)
    if row is None:
        raise HTTPException(status_code=404, detail="Anomaly run not found")
    return row


@router.get("/runs/{id}/results", dependencies=[Depends(anomaly_engine_control_plane_dependency(action="anomaly_engine_view", resource_type="anomaly_result"))])
async def list_results(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    return await _build_service(session).list_results(tenant_id=user.tenant_id, run_id=id)


@router.get("/runs/{id}/signals", dependencies=[Depends(anomaly_engine_control_plane_dependency(action="anomaly_engine_view", resource_type="anomaly_contributing_signal"))])
async def list_signals(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    return await _build_service(session).list_signals(tenant_id=user.tenant_id, run_id=id)


@router.get("/runs/{id}/rollforwards", dependencies=[Depends(anomaly_engine_control_plane_dependency(action="anomaly_engine_view", resource_type="anomaly_rollforward_event"))])
async def list_rollforwards(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    return await _build_service(session).list_rollforwards(tenant_id=user.tenant_id, run_id=id)


@router.get("/runs/{id}/evidence", dependencies=[Depends(anomaly_engine_control_plane_dependency(action="anomaly_engine_evidence_view", resource_type="anomaly_evidence_link"))])
async def list_evidence(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    return await _build_service(session).list_evidence(tenant_id=user.tenant_id, run_id=id)
