from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user
from financeops.db.models.users import IamUser
from financeops.modules.financial_risk_engine.api.schemas import (
    RiskDefinitionCreateRequest,
    RiskMaterialityRuleCreateRequest,
    RiskRunCreateRequest,
    RiskRunCreateResponse,
    RiskRunExecuteResponse,
    RiskWeightCreateRequest,
)
from financeops.modules.financial_risk_engine.application.materiality_service import (
    MaterialityService,
)
from financeops.modules.financial_risk_engine.application.run_service import RunService
from financeops.modules.financial_risk_engine.application.scoring_service import ScoringService
from financeops.modules.financial_risk_engine.application.validation_service import (
    ValidationService,
)
from financeops.modules.financial_risk_engine.domain.value_objects import (
    DefinitionVersionTokenInput,
)
from financeops.modules.financial_risk_engine.infrastructure.repository import (
    FinancialRiskRepository,
)
from financeops.modules.financial_risk_engine.infrastructure.token_builder import (
    build_definition_version_token,
)
from financeops.modules.financial_risk_engine.policies.control_plane_policy import (
    financial_risk_control_plane_dependency,
)

router = APIRouter()


def _build_run_service(session: AsyncSession) -> RunService:
    return RunService(
        repository=FinancialRiskRepository(session),
        validation_service=ValidationService(),
        scoring_service=ScoringService(),
        materiality_service=MaterialityService(),
    )


@router.post(
    "/risk-definitions",
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(
            financial_risk_control_plane_dependency(
                action="risk_definition_manage",
                resource_type="risk_definition",
            )
        )
    ],
)
async def create_risk_definition(
    body: RiskDefinitionCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    repository = FinancialRiskRepository(session)
    version_token = build_definition_version_token(
        DefinitionVersionTokenInput(
            rows=[
                {
                    "risk_code": body.risk_code,
                    "risk_name": body.risk_name,
                    "risk_domain": body.risk_domain,
                    "signal_selector_json": body.signal_selector_json,
                    "definition_json": body.definition_json,
                    "effective_from": body.effective_from.isoformat(),
                    "effective_to": body.effective_to.isoformat() if body.effective_to else None,
                    "status": body.status,
                    "dependencies": [
                        {
                            "dependency_type": row.dependency_type,
                            "depends_on_risk_definition_id": (
                                str(row.depends_on_risk_definition_id)
                                if row.depends_on_risk_definition_id
                                else None
                            ),
                            "signal_reference_code": row.signal_reference_code,
                            "propagation_factor": str(row.propagation_factor),
                            "amplification_rule_json": row.amplification_rule_json,
                            "attenuation_rule_json": row.attenuation_rule_json,
                            "cap_limit": str(row.cap_limit),
                        }
                        for row in sorted(
                            body.dependencies,
                            key=lambda item: (
                                item.dependency_type,
                                str(item.depends_on_risk_definition_id or ""),
                                item.signal_reference_code or "",
                            ),
                        )
                    ],
                }
            ]
        )
    )
    try:
        row = await repository.create_risk_definition(
            tenant_id=user.tenant_id,
            organisation_id=body.organisation_id,
            risk_code=body.risk_code,
            risk_name=body.risk_name,
            risk_domain=body.risk_domain,
            signal_selector_json=body.signal_selector_json,
            definition_json=body.definition_json,
            version_token=version_token,
            effective_from=body.effective_from,
            effective_to=body.effective_to,
            supersedes_id=body.supersedes_id,
            status=body.status,
            dependencies=[row.model_dump() for row in body.dependencies],
            created_by=user.id,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail="internal_error") from exc
    await session.flush()
    return {
        "id": str(row.id),
        "risk_code": row.risk_code,
        "version_token": row.version_token,
        "status": row.status,
    }


@router.get(
    "/risk-definitions",
    dependencies=[
        Depends(
            financial_risk_control_plane_dependency(
                action="financial_risk_view",
                resource_type="risk_definition",
            )
        )
    ],
)
async def list_risk_definitions(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    repository = FinancialRiskRepository(session)
    rows = await repository.list_risk_definitions(tenant_id=user.tenant_id)
    return [
        {
            "id": str(row.id),
            "risk_code": row.risk_code,
            "risk_name": row.risk_name,
            "risk_domain": row.risk_domain,
            "version_token": row.version_token,
            "status": row.status,
            "effective_from": row.effective_from.isoformat(),
            "effective_to": row.effective_to.isoformat() if row.effective_to else None,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]


@router.get(
    "/risk-definitions/{id}/versions",
    dependencies=[
        Depends(
            financial_risk_control_plane_dependency(
                action="financial_risk_view",
                resource_type="risk_definition",
            )
        )
    ],
)
async def list_risk_definition_versions(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    repository = FinancialRiskRepository(session)
    rows = await repository.list_risk_definition_versions(
        tenant_id=user.tenant_id,
        definition_id=id,
    )
    return [
        {
            "id": str(row.id),
            "risk_code": row.risk_code,
            "risk_name": row.risk_name,
            "risk_domain": row.risk_domain,
            "version_token": row.version_token,
            "status": row.status,
            "effective_from": row.effective_from.isoformat(),
        }
        for row in rows
    ]


@router.post(
    "/risk-weights",
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(
            financial_risk_control_plane_dependency(
                action="risk_weight_manage",
                resource_type="risk_weight_configuration",
            )
        )
    ],
)
async def create_risk_weight(
    body: RiskWeightCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    repository = FinancialRiskRepository(session)
    version_token = build_definition_version_token(
        DefinitionVersionTokenInput(
            rows=[
                {
                    "weight_code": body.weight_code,
                    "risk_code": body.risk_code,
                    "scope_type": body.scope_type,
                    "scope_value": body.scope_value,
                    "weight_value": str(body.weight_value),
                    "board_critical_override": body.board_critical_override,
                    "configuration_json": body.configuration_json,
                    "effective_from": body.effective_from.isoformat(),
                    "status": body.status,
                }
            ]
        )
    )
    try:
        row = await repository.create_weight_configuration(
            tenant_id=user.tenant_id,
            organisation_id=body.organisation_id,
            weight_code=body.weight_code,
            risk_code=body.risk_code,
            scope_type=body.scope_type,
            scope_value=body.scope_value,
            weight_value=body.weight_value,
            board_critical_override=body.board_critical_override,
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
        "weight_code": row.weight_code,
        "version_token": row.version_token,
        "status": row.status,
    }

@router.get(
    "/risk-weights",
    dependencies=[
        Depends(
            financial_risk_control_plane_dependency(
                action="financial_risk_view",
                resource_type="risk_weight_configuration",
            )
        )
    ],
)
async def list_risk_weights(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    repository = FinancialRiskRepository(session)
    rows = await repository.list_weight_configurations(tenant_id=user.tenant_id)
    return [
        {
            "id": str(row.id),
            "weight_code": row.weight_code,
            "risk_code": row.risk_code,
            "scope_type": row.scope_type,
            "scope_value": row.scope_value,
            "weight_value": str(row.weight_value),
            "version_token": row.version_token,
            "status": row.status,
            "effective_from": row.effective_from.isoformat(),
        }
        for row in rows
    ]


@router.get(
    "/risk-weights/{id}/versions",
    dependencies=[
        Depends(
            financial_risk_control_plane_dependency(
                action="financial_risk_view",
                resource_type="risk_weight_configuration",
            )
        )
    ],
)
async def list_risk_weight_versions(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    repository = FinancialRiskRepository(session)
    rows = await repository.list_weight_versions(tenant_id=user.tenant_id, weight_id=id)
    return [
        {
            "id": str(row.id),
            "weight_code": row.weight_code,
            "risk_code": row.risk_code,
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
            financial_risk_control_plane_dependency(
                action="risk_materiality_manage",
                resource_type="risk_materiality_rule",
            )
        )
    ],
)
async def create_materiality_rule(
    body: RiskMaterialityRuleCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    repository = FinancialRiskRepository(session)
    version_token = build_definition_version_token(
        DefinitionVersionTokenInput(
            rows=[
                {
                    "rule_code": body.rule_code,
                    "rule_name": body.rule_name,
                    "threshold_json": body.threshold_json,
                    "severity_mapping_json": body.severity_mapping_json,
                    "propagation_behavior_json": body.propagation_behavior_json,
                    "escalation_rule_json": body.escalation_rule_json,
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
            rule_code=body.rule_code,
            rule_name=body.rule_name,
            threshold_json=body.threshold_json,
            severity_mapping_json=body.severity_mapping_json,
            propagation_behavior_json=body.propagation_behavior_json,
            escalation_rule_json=body.escalation_rule_json,
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
        "rule_code": row.rule_code,
        "version_token": row.version_token,
        "status": row.status,
    }


@router.get(
    "/materiality-rules",
    dependencies=[
        Depends(
            financial_risk_control_plane_dependency(
                action="financial_risk_view",
                resource_type="risk_materiality_rule",
            )
        )
    ],
)
async def list_materiality_rules(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    repository = FinancialRiskRepository(session)
    rows = await repository.list_materiality_rules(tenant_id=user.tenant_id)
    return [
        {
            "id": str(row.id),
            "rule_code": row.rule_code,
            "rule_name": row.rule_name,
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
            financial_risk_control_plane_dependency(
                action="financial_risk_view",
                resource_type="risk_materiality_rule",
            )
        )
    ],
)
async def list_materiality_rule_versions(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    repository = FinancialRiskRepository(session)
    rows = await repository.list_materiality_rule_versions(
        tenant_id=user.tenant_id,
        rule_id=id,
    )
    return [
        {
            "id": str(row.id),
            "rule_code": row.rule_code,
            "rule_name": row.rule_name,
            "version_token": row.version_token,
            "status": row.status,
            "effective_from": row.effective_from.isoformat(),
        }
        for row in rows
    ]


@router.post(
    "/runs",
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(
            financial_risk_control_plane_dependency(
                action="financial_risk_run",
                resource_type="risk_run",
            )
        )
    ],
    response_model=RiskRunCreateResponse,
)
async def create_run(
    body: RiskRunCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    service = _build_run_service(session)
    try:
        payload = await service.create_run(
            tenant_id=user.tenant_id,
            organisation_id=body.organisation_id,
            reporting_period=body.reporting_period,
            source_metric_run_ids=body.source_metric_run_ids,
            source_variance_run_ids=body.source_variance_run_ids,
            source_trend_run_ids=body.source_trend_run_ids,
            source_reconciliation_session_ids=body.source_reconciliation_session_ids,
            created_by=user.id,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail="internal_error") from exc
    await session.flush()
    return payload


@router.post(
    "/runs/{id}/execute",
    dependencies=[
        Depends(
            financial_risk_control_plane_dependency(
                action="financial_risk_run",
                resource_type="risk_run",
            )
        )
    ],
    response_model=RiskRunExecuteResponse,
)
async def execute_run(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    service = _build_run_service(session)
    try:
        payload = await service.execute_run(
            tenant_id=user.tenant_id,
            run_id=id,
            actor_user_id=user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="internal_error") from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail="internal_error") from exc
    await session.flush()
    return payload

@router.get(
    "/runs/{id}",
    dependencies=[
        Depends(
            financial_risk_control_plane_dependency(
                action="financial_risk_view",
                resource_type="risk_run",
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
        raise HTTPException(status_code=404, detail="Risk run not found")
    return row


@router.get(
    "/runs/{id}/summary",
    dependencies=[
        Depends(
            financial_risk_control_plane_dependency(
                action="financial_risk_view",
                resource_type="risk_run",
            )
        )
    ],
)
async def get_run_summary(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    service = _build_run_service(session)
    try:
        return await service.summary(tenant_id=user.tenant_id, run_id=id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="internal_error") from exc


@router.get(
    "/runs/{id}/results",
    dependencies=[
        Depends(
            financial_risk_control_plane_dependency(
                action="financial_risk_view",
                resource_type="risk_result",
            )
        )
    ],
)
async def list_run_results(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    service = _build_run_service(session)
    return await service.list_results(tenant_id=user.tenant_id, run_id=id)


@router.get(
    "/runs/{id}/signals",
    dependencies=[
        Depends(
            financial_risk_control_plane_dependency(
                action="financial_risk_view",
                resource_type="risk_contributing_signal",
            )
        )
    ],
)
async def list_run_signals(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    service = _build_run_service(session)
    return await service.list_signals(tenant_id=user.tenant_id, run_id=id)


@router.get(
    "/runs/{id}/rollforwards",
    dependencies=[
        Depends(
            financial_risk_control_plane_dependency(
                action="financial_risk_view",
                resource_type="risk_rollforward_event",
            )
        )
    ],
)
async def list_run_rollforwards(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    service = _build_run_service(session)
    return await service.list_rollforwards(tenant_id=user.tenant_id, run_id=id)


@router.get(
    "/runs/{id}/evidence",
    dependencies=[
        Depends(
            financial_risk_control_plane_dependency(
                action="financial_risk_evidence_view",
                resource_type="risk_evidence_link",
            )
        )
    ],
)
async def list_run_evidence(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    service = _build_run_service(session)
    return await service.list_evidence(tenant_id=user.tenant_id, run_id=id)
