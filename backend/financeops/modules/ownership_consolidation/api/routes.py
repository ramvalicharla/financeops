from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user
from financeops.db.models.users import IamUser
from financeops.modules.ownership_consolidation.api.schemas import (
    MinorityInterestRuleCreateRequest,
    OwnershipRelationshipCreateRequest,
    OwnershipRuleCreateRequest,
    OwnershipRunCreateRequest,
    OwnershipRunCreateResponse,
    OwnershipRunExecuteResponse,
    OwnershipStructureCreateRequest,
)
from financeops.modules.ownership_consolidation.application.mapping_service import MappingService
from financeops.modules.ownership_consolidation.application.rule_service import RuleService
from financeops.modules.ownership_consolidation.application.run_service import RunService
from financeops.modules.ownership_consolidation.application.validation_service import (
    ValidationService,
)
from financeops.modules.ownership_consolidation.domain.value_objects import (
    DefinitionVersionTokenInput,
)
from financeops.modules.ownership_consolidation.infrastructure.repository import (
    OwnershipConsolidationRepository,
)
from financeops.modules.ownership_consolidation.infrastructure.token_builder import (
    build_definition_version_token,
)
from financeops.modules.ownership_consolidation.policies.control_plane_policy import (
    ownership_consolidation_control_plane_dependency,
)

router = APIRouter()


def _build_service(session: AsyncSession) -> RunService:
    return RunService(
        repository=OwnershipConsolidationRepository(session),
        validation_service=ValidationService(),
        mapping_service=MappingService(),
        rule_service=RuleService(),
    )


@router.post(
    "/structures",
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(
            ownership_consolidation_control_plane_dependency(
                action="ownership_structure_manage",
                resource_type="ownership_structure_definition",
            )
        )
    ],
)
async def create_structure(
    body: OwnershipStructureCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    repository = OwnershipConsolidationRepository(session)
    version_token = build_definition_version_token(
        DefinitionVersionTokenInput(rows=[body.model_dump(mode="json")])
    )
    try:
        row = await repository.create_structure_definition(
            tenant_id=user.tenant_id,
            organisation_id=body.organisation_id,
            ownership_structure_code=body.ownership_structure_code,
            ownership_structure_name=body.ownership_structure_name,
            hierarchy_scope_ref=body.hierarchy_scope_ref,
            ownership_basis_type=body.ownership_basis_type,
            version_token=version_token,
            effective_from=body.effective_from,
            effective_to=body.effective_to,
            supersedes_id=body.supersedes_id,
            status=body.status,
            created_by=user.id,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await session.commit()
    return {
        "id": str(row.id),
        "ownership_structure_code": row.ownership_structure_code,
        "version_token": row.version_token,
        "status": row.status,
    }


@router.get(
    "/structures",
    dependencies=[
        Depends(
            ownership_consolidation_control_plane_dependency(
                action="ownership_consolidation_view",
                resource_type="ownership_structure_definition",
            )
        )
    ],
)
async def list_structures(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    rows = await OwnershipConsolidationRepository(session).list_structure_definitions(
        tenant_id=user.tenant_id
    )
    return [
        {
            "id": str(row.id),
            "ownership_structure_code": row.ownership_structure_code,
            "ownership_structure_name": row.ownership_structure_name,
            "ownership_basis_type": row.ownership_basis_type,
            "version_token": row.version_token,
            "status": row.status,
        }
        for row in rows
    ]


@router.get(
    "/structures/{id}/versions",
    dependencies=[
        Depends(
            ownership_consolidation_control_plane_dependency(
                action="ownership_consolidation_view",
                resource_type="ownership_structure_definition",
            )
        )
    ],
)
async def list_structure_versions(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    rows = await OwnershipConsolidationRepository(session).list_structure_versions(
        tenant_id=user.tenant_id, definition_id=id
    )
    return [
        {
            "id": str(row.id),
            "ownership_structure_code": row.ownership_structure_code,
            "version_token": row.version_token,
            "status": row.status,
            "effective_from": row.effective_from.isoformat(),
        }
        for row in rows
    ]


@router.post(
    "/relationships",
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(
            ownership_consolidation_control_plane_dependency(
                action="ownership_relationship_manage",
                resource_type="ownership_relationship",
            )
        )
    ],
)
async def create_relationship(
    body: OwnershipRelationshipCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    repository = OwnershipConsolidationRepository(session)
    try:
        row = await repository.create_relationship(
            tenant_id=user.tenant_id,
            organisation_id=body.organisation_id,
            ownership_structure_id=body.ownership_structure_id,
            parent_entity_id=body.parent_entity_id,
            child_entity_id=body.child_entity_id,
            ownership_percentage=body.ownership_percentage,
            voting_percentage_nullable=body.voting_percentage_nullable,
            control_indicator=body.control_indicator,
            minority_interest_indicator=body.minority_interest_indicator,
            proportionate_consolidation_indicator=body.proportionate_consolidation_indicator,
            effective_from=body.effective_from,
            effective_to=body.effective_to,
            supersedes_id=body.supersedes_id,
            status=body.status,
            created_by=user.id,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await session.commit()
    return {
        "id": str(row.id),
        "ownership_structure_id": str(row.ownership_structure_id),
        "parent_entity_id": str(row.parent_entity_id),
        "child_entity_id": str(row.child_entity_id),
        "status": row.status,
    }


@router.get(
    "/relationships",
    dependencies=[
        Depends(
            ownership_consolidation_control_plane_dependency(
                action="ownership_consolidation_view",
                resource_type="ownership_relationship",
            )
        )
    ],
)
async def list_relationships(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    rows = await OwnershipConsolidationRepository(session).list_relationships(
        tenant_id=user.tenant_id
    )
    return [
        {
            "id": str(row.id),
            "ownership_structure_id": str(row.ownership_structure_id),
            "parent_entity_id": str(row.parent_entity_id),
            "child_entity_id": str(row.child_entity_id),
            "ownership_percentage": str(row.ownership_percentage),
            "proportionate_consolidation_indicator": bool(
                row.proportionate_consolidation_indicator
            ),
            "minority_interest_indicator": bool(row.minority_interest_indicator),
            "status": row.status,
        }
        for row in rows
    ]


@router.get(
    "/relationships/{id}/versions",
    dependencies=[
        Depends(
            ownership_consolidation_control_plane_dependency(
                action="ownership_consolidation_view",
                resource_type="ownership_relationship",
            )
        )
    ],
)
async def list_relationship_versions(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    rows = await OwnershipConsolidationRepository(session).list_relationship_versions(
        tenant_id=user.tenant_id,
        relationship_id=id,
    )
    return [
        {
            "id": str(row.id),
            "ownership_structure_id": str(row.ownership_structure_id),
            "parent_entity_id": str(row.parent_entity_id),
            "child_entity_id": str(row.child_entity_id),
            "ownership_percentage": str(row.ownership_percentage),
            "status": row.status,
            "effective_from": row.effective_from.isoformat(),
        }
        for row in rows
    ]


@router.post(
    "/rules",
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(
            ownership_consolidation_control_plane_dependency(
                action="ownership_rule_manage",
                resource_type="ownership_consolidation_rule_definition",
            )
        )
    ],
)
async def create_ownership_rule(
    body: OwnershipRuleCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    repository = OwnershipConsolidationRepository(session)
    version_token = build_definition_version_token(
        DefinitionVersionTokenInput(rows=[body.model_dump(mode="json")])
    )
    try:
        row = await repository.create_ownership_rule_definition(
            tenant_id=user.tenant_id,
            organisation_id=body.organisation_id,
            rule_code=body.rule_code,
            rule_name=body.rule_name,
            rule_type=body.rule_type,
            rule_logic_json=body.rule_logic_json,
            attribution_policy_json=body.attribution_policy_json,
            version_token=version_token,
            effective_from=body.effective_from,
            effective_to=body.effective_to,
            supersedes_id=body.supersedes_id,
            status=body.status,
            created_by=user.id,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await session.commit()
    return {"id": str(row.id), "rule_code": row.rule_code, "version_token": row.version_token}


@router.get(
    "/rules",
    dependencies=[
        Depends(
            ownership_consolidation_control_plane_dependency(
                action="ownership_consolidation_view",
                resource_type="ownership_consolidation_rule_definition",
            )
        )
    ],
)
async def list_ownership_rules(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    rows = await OwnershipConsolidationRepository(session).list_ownership_rule_definitions(
        tenant_id=user.tenant_id
    )
    return [
        {
            "id": str(row.id),
            "rule_code": row.rule_code,
            "rule_name": row.rule_name,
            "rule_type": row.rule_type,
            "version_token": row.version_token,
            "status": row.status,
        }
        for row in rows
    ]


@router.get(
    "/rules/{id}/versions",
    dependencies=[
        Depends(
            ownership_consolidation_control_plane_dependency(
                action="ownership_consolidation_view",
                resource_type="ownership_consolidation_rule_definition",
            )
        )
    ],
)
async def list_ownership_rule_versions(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    rows = await OwnershipConsolidationRepository(session).list_ownership_rule_versions(
        tenant_id=user.tenant_id,
        rule_id=id,
    )
    return [
        {
            "id": str(row.id),
            "rule_code": row.rule_code,
            "version_token": row.version_token,
            "status": row.status,
            "effective_from": row.effective_from.isoformat(),
        }
        for row in rows
    ]


@router.post(
    "/minority-interest-rules",
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(
            ownership_consolidation_control_plane_dependency(
                action="minority_interest_rule_manage",
                resource_type="minority_interest_rule_definition",
            )
        )
    ],
)
async def create_minority_interest_rule(
    body: MinorityInterestRuleCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    repository = OwnershipConsolidationRepository(session)
    version_token = build_definition_version_token(
        DefinitionVersionTokenInput(rows=[body.model_dump(mode="json")])
    )
    try:
        row = await repository.create_minority_interest_rule_definition(
            tenant_id=user.tenant_id,
            organisation_id=body.organisation_id,
            rule_code=body.rule_code,
            rule_name=body.rule_name,
            attribution_basis_type=body.attribution_basis_type,
            calculation_logic_json=body.calculation_logic_json,
            presentation_logic_json=body.presentation_logic_json,
            version_token=version_token,
            effective_from=body.effective_from,
            effective_to=body.effective_to,
            supersedes_id=body.supersedes_id,
            status=body.status,
            created_by=user.id,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await session.commit()
    return {"id": str(row.id), "rule_code": row.rule_code, "version_token": row.version_token}


@router.get(
    "/minority-interest-rules",
    dependencies=[
        Depends(
            ownership_consolidation_control_plane_dependency(
                action="ownership_consolidation_view",
                resource_type="minority_interest_rule_definition",
            )
        )
    ],
)
async def list_minority_interest_rules(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    rows = await OwnershipConsolidationRepository(session).list_minority_interest_rule_definitions(
        tenant_id=user.tenant_id
    )
    return [
        {
            "id": str(row.id),
            "rule_code": row.rule_code,
            "rule_name": row.rule_name,
            "attribution_basis_type": row.attribution_basis_type,
            "version_token": row.version_token,
            "status": row.status,
        }
        for row in rows
    ]


@router.get(
    "/minority-interest-rules/{id}/versions",
    dependencies=[
        Depends(
            ownership_consolidation_control_plane_dependency(
                action="ownership_consolidation_view",
                resource_type="minority_interest_rule_definition",
            )
        )
    ],
)
async def list_minority_interest_rule_versions(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    rows = await OwnershipConsolidationRepository(session).list_minority_interest_rule_versions(
        tenant_id=user.tenant_id,
        rule_id=id,
    )
    return [
        {
            "id": str(row.id),
            "rule_code": row.rule_code,
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
            ownership_consolidation_control_plane_dependency(
                action="ownership_consolidation_run",
                resource_type="ownership_consolidation_run",
            )
        )
    ],
    response_model=OwnershipRunCreateResponse,
)
async def create_run(
    body: OwnershipRunCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> OwnershipRunCreateResponse:
    try:
        response = await _build_service(session).create_run(
            tenant_id=user.tenant_id,
            organisation_id=body.organisation_id,
            reporting_period=body.reporting_period,
            source_consolidation_run_refs=[
                {"source_type": ref.source_type, "run_id": str(ref.run_id)}
                for ref in body.source_consolidation_run_refs
            ],
            fx_translation_run_ref_nullable=body.fx_translation_run_ref_nullable,
            created_by=user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await session.commit()
    return OwnershipRunCreateResponse(**response)


@router.post(
    "/runs/{id}/execute",
    dependencies=[
        Depends(
            ownership_consolidation_control_plane_dependency(
                action="ownership_consolidation_run",
                resource_type="ownership_consolidation_run",
            )
        )
    ],
    response_model=OwnershipRunExecuteResponse,
)
async def execute_run(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> OwnershipRunExecuteResponse:
    try:
        response = await _build_service(session).execute_run(
            tenant_id=user.tenant_id,
            run_id=id,
            created_by=user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await session.commit()
    return OwnershipRunExecuteResponse(**response)


@router.get(
    "/runs/{id}",
    dependencies=[
        Depends(
            ownership_consolidation_control_plane_dependency(
                action="ownership_consolidation_view",
                resource_type="ownership_consolidation_run",
            )
        )
    ],
)
async def get_run(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    row = await _build_service(session).get_run(tenant_id=user.tenant_id, run_id=id)
    if row is None:
        raise HTTPException(status_code=404, detail="Ownership consolidation run not found")
    return row


@router.get(
    "/runs/{id}/summary",
    dependencies=[
        Depends(
            ownership_consolidation_control_plane_dependency(
                action="ownership_consolidation_view",
                resource_type="ownership_consolidation_run",
            )
        )
    ],
)
async def get_run_summary(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    try:
        return await _build_service(session).summary(tenant_id=user.tenant_id, run_id=id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/runs/{id}/metrics",
    dependencies=[
        Depends(
            ownership_consolidation_control_plane_dependency(
                action="ownership_consolidation_view",
                resource_type="ownership_consolidation_metric_result",
            )
        )
    ],
)
async def list_metrics(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    return await _build_service(session).list_metrics(tenant_id=user.tenant_id, run_id=id)


@router.get(
    "/runs/{id}/variances",
    dependencies=[
        Depends(
            ownership_consolidation_control_plane_dependency(
                action="ownership_consolidation_view",
                resource_type="ownership_consolidation_variance_result",
            )
        )
    ],
)
async def list_variances(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    return await _build_service(session).list_variances(tenant_id=user.tenant_id, run_id=id)


@router.get(
    "/runs/{id}/risks",
    dependencies=[
        Depends(
            ownership_consolidation_control_plane_dependency(
                action="ownership_consolidation_view",
                resource_type="risk_result",
            )
        )
    ],
)
async def list_risks(_: uuid.UUID) -> list[dict]:
    return []


@router.get(
    "/runs/{id}/anomalies",
    dependencies=[
        Depends(
            ownership_consolidation_control_plane_dependency(
                action="ownership_consolidation_view",
                resource_type="anomaly_result",
            )
        )
    ],
)
async def list_anomalies(_: uuid.UUID) -> list[dict]:
    return []


@router.get(
    "/runs/{id}/board-pack",
    dependencies=[
        Depends(
            ownership_consolidation_control_plane_dependency(
                action="ownership_consolidation_view",
                resource_type="board_pack_result",
            )
        )
    ],
)
async def get_board_pack(_: uuid.UUID) -> dict:
    return {"status": "not_generated", "sections": []}


@router.get(
    "/runs/{id}/evidence",
    dependencies=[
        Depends(
            ownership_consolidation_control_plane_dependency(
                action="ownership_consolidation_evidence_view",
                resource_type="ownership_consolidation_evidence_link",
            )
        )
    ],
)
async def list_evidence(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    return await _build_service(session).list_evidence(tenant_id=user.tenant_id, run_id=id)
