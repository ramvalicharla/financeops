from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user
from financeops.db.models.users import IamUser
from financeops.modules.multi_entity_consolidation.api.schemas import (
    ConsolidationAdjustmentCreateRequest,
    ConsolidationRuleCreateRequest,
    ConsolidationRunCreateRequest,
    ConsolidationRunCreateResponse,
    ConsolidationRunExecuteResponse,
    ConsolidationScopeCreateRequest,
    EntityHierarchyCreateRequest,
    IntercompanyRuleCreateRequest,
)
from financeops.modules.multi_entity_consolidation.application.adjustment_service import (
    AdjustmentService,
)
from financeops.modules.multi_entity_consolidation.application.aggregation_service import (
    AggregationService,
)
from financeops.modules.multi_entity_consolidation.application.hierarchy_service import (
    HierarchyService,
)
from financeops.modules.multi_entity_consolidation.application.intercompany_service import (
    IntercompanyService,
)
from financeops.modules.multi_entity_consolidation.application.run_service import RunService
from financeops.modules.multi_entity_consolidation.application.validation_service import (
    ValidationService,
)
from financeops.modules.multi_entity_consolidation.domain.value_objects import (
    DefinitionVersionTokenInput,
)
from financeops.modules.multi_entity_consolidation.infrastructure.repository import (
    MultiEntityConsolidationRepository,
)
from financeops.modules.multi_entity_consolidation.infrastructure.token_builder import (
    build_definition_version_token,
)
from financeops.modules.multi_entity_consolidation.policies.control_plane_policy import (
    consolidation_control_plane_dependency,
)

router = APIRouter()


def _build_service(session: AsyncSession) -> RunService:
    return RunService(
        repository=MultiEntityConsolidationRepository(session),
        validation_service=ValidationService(),
        hierarchy_service=HierarchyService(),
        aggregation_service=AggregationService(),
        intercompany_service=IntercompanyService(),
        adjustment_service=AdjustmentService(),
    )


@router.post(
    "/hierarchies",
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(
            consolidation_control_plane_dependency(
                action="entity_hierarchy_manage",
                resource_type="entity_hierarchy",
            )
        )
    ],
)
async def create_hierarchy(
    body: EntityHierarchyCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    repository = MultiEntityConsolidationRepository(session)
    payload = body.model_dump(mode="json")
    version_token = build_definition_version_token(DefinitionVersionTokenInput(rows=[payload]))
    try:
        hierarchy = await repository.create_entity_hierarchy(
            tenant_id=user.tenant_id,
            organisation_id=body.organisation_id,
            hierarchy_code=body.hierarchy_code,
            hierarchy_name=body.hierarchy_name,
            hierarchy_type=body.hierarchy_type,
            version_token=version_token,
            effective_from=body.effective_from,
            effective_to=body.effective_to,
            supersedes_id=body.supersedes_id,
            status=body.status,
            created_by=user.id,
        )
        if body.nodes:
            nodes = sorted(body.nodes, key=lambda item: (item.node_level, item.node_key))
            created_by_key: dict[str, uuid.UUID] = {}
            to_create: list[dict] = []
            for node in nodes:
                parent_id = (
                    created_by_key[node.parent_node_temp_key]
                    if node.parent_node_temp_key is not None
                    else None
                )
                node_id = uuid.uuid4()
                created_by_key[node.node_key] = node_id
                to_create.append(
                    {
                        "id": node_id,
                        "hierarchy_id": hierarchy.id,
                        "entity_id": node.entity_id,
                        "parent_node_id": parent_id,
                        "node_level": node.node_level,
                        "effective_from": node.effective_from,
                        "effective_to": node.effective_to,
                        "supersedes_id": node.supersedes_id,
                        "status": node.status,
                    }
                )
            await repository.create_entity_hierarchy_nodes(
                tenant_id=user.tenant_id,
                created_by=user.id,
                rows=to_create,
            )
    except Exception as exc:
        raise HTTPException(status_code=400, detail="internal_error") from exc
    await session.flush()
    return {
        "id": str(hierarchy.id),
        "hierarchy_code": hierarchy.hierarchy_code,
        "version_token": hierarchy.version_token,
        "status": hierarchy.status,
    }


@router.get(
    "/hierarchies",
    dependencies=[
        Depends(
            consolidation_control_plane_dependency(
                action="consolidation_view",
                resource_type="entity_hierarchy",
            )
        )
    ],
)
async def list_hierarchies(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    rows = await MultiEntityConsolidationRepository(session).list_entity_hierarchies(
        tenant_id=user.tenant_id
    )
    return [
        {
            "id": str(row.id),
            "hierarchy_code": row.hierarchy_code,
            "hierarchy_name": row.hierarchy_name,
            "hierarchy_type": row.hierarchy_type,
            "version_token": row.version_token,
            "status": row.status,
        }
        for row in rows
    ]


@router.get(
    "/hierarchies/{id}/versions",
    dependencies=[
        Depends(
            consolidation_control_plane_dependency(
                action="consolidation_view",
                resource_type="entity_hierarchy",
            )
        )
    ],
)
async def list_hierarchy_versions(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    rows = await MultiEntityConsolidationRepository(session).list_entity_hierarchy_versions(
        tenant_id=user.tenant_id,
        hierarchy_id=id,
    )
    return [
        {
            "id": str(row.id),
            "hierarchy_code": row.hierarchy_code,
            "version_token": row.version_token,
            "status": row.status,
            "effective_from": row.effective_from.isoformat(),
        }
        for row in rows
    ]


@router.post(
    "/scopes",
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(
            consolidation_control_plane_dependency(
                action="consolidation_scope_manage",
                resource_type="consolidation_scope",
            )
        )
    ],
)
async def create_scope(
    body: ConsolidationScopeCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    repository = MultiEntityConsolidationRepository(session)
    version_token = build_definition_version_token(
        DefinitionVersionTokenInput(rows=[body.model_dump(mode="json")])
    )
    try:
        row = await repository.create_scope(
            tenant_id=user.tenant_id,
            organisation_id=body.organisation_id,
            scope_code=body.scope_code,
            scope_name=body.scope_name,
            hierarchy_id=body.hierarchy_id,
            scope_selector_json=body.scope_selector_json,
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
    return {"id": str(row.id), "scope_code": row.scope_code, "version_token": row.version_token}


@router.get(
    "/scopes",
    dependencies=[
        Depends(
            consolidation_control_plane_dependency(
                action="consolidation_view",
                resource_type="consolidation_scope",
            )
        )
    ],
)
async def list_scopes(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    rows = await MultiEntityConsolidationRepository(session).list_scopes(tenant_id=user.tenant_id)
    return [
        {
            "id": str(row.id),
            "scope_code": row.scope_code,
            "scope_name": row.scope_name,
            "version_token": row.version_token,
            "status": row.status,
        }
        for row in rows
    ]


@router.get(
    "/scopes/{id}/versions",
    dependencies=[
        Depends(
            consolidation_control_plane_dependency(
                action="consolidation_view",
                resource_type="consolidation_scope",
            )
        )
    ],
)
async def list_scope_versions(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    rows = await MultiEntityConsolidationRepository(session).list_scope_versions(
        tenant_id=user.tenant_id, scope_id=id
    )
    return [
        {
            "id": str(row.id),
            "scope_code": row.scope_code,
            "version_token": row.version_token,
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
            consolidation_control_plane_dependency(
                action="consolidation_rule_manage",
                resource_type="consolidation_rule_definition",
            )
        )
    ],
)
async def create_rule(
    body: ConsolidationRuleCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    repository = MultiEntityConsolidationRepository(session)
    version_token = build_definition_version_token(
        DefinitionVersionTokenInput(rows=[body.model_dump(mode="json")])
    )
    try:
        row = await repository.create_rule_definition(
            tenant_id=user.tenant_id,
            organisation_id=body.organisation_id,
            rule_code=body.rule_code,
            rule_name=body.rule_name,
            rule_type=body.rule_type,
            rule_logic_json=body.rule_logic_json,
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
    return {"id": str(row.id), "rule_code": row.rule_code, "version_token": row.version_token}


@router.get(
    "/rules",
    dependencies=[
        Depends(
            consolidation_control_plane_dependency(
                action="consolidation_view",
                resource_type="consolidation_rule_definition",
            )
        )
    ],
)
async def list_rules(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    rows = await MultiEntityConsolidationRepository(session).list_rule_definitions(
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
            consolidation_control_plane_dependency(
                action="consolidation_view",
                resource_type="consolidation_rule_definition",
            )
        )
    ],
)
async def list_rule_versions(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    rows = await MultiEntityConsolidationRepository(session).list_rule_versions(
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
    "/intercompany-rules",
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(
            consolidation_control_plane_dependency(
                action="intercompany_rule_manage",
                resource_type="intercompany_mapping_rule",
            )
        )
    ],
)
async def create_intercompany_rule(
    body: IntercompanyRuleCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    repository = MultiEntityConsolidationRepository(session)
    version_token = build_definition_version_token(
        DefinitionVersionTokenInput(rows=[body.model_dump(mode="json")])
    )
    try:
        row = await repository.create_intercompany_rule(
            tenant_id=user.tenant_id,
            organisation_id=body.organisation_id,
            rule_code=body.rule_code,
            source_selector_json=body.source_selector_json,
            counterpart_selector_json=body.counterpart_selector_json,
            treatment_rule_json=body.treatment_rule_json,
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
    return {"id": str(row.id), "rule_code": row.rule_code, "version_token": row.version_token}


@router.get(
    "/intercompany-rules",
    dependencies=[
        Depends(
            consolidation_control_plane_dependency(
                action="consolidation_view",
                resource_type="intercompany_mapping_rule",
            )
        )
    ],
)
async def list_intercompany_rules(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    rows = await MultiEntityConsolidationRepository(session).list_intercompany_rules(
        tenant_id=user.tenant_id
    )
    return [
        {
            "id": str(row.id),
            "rule_code": row.rule_code,
            "version_token": row.version_token,
            "status": row.status,
        }
        for row in rows
    ]


@router.get(
    "/intercompany-rules/{id}/versions",
    dependencies=[
        Depends(
            consolidation_control_plane_dependency(
                action="consolidation_view",
                resource_type="intercompany_mapping_rule",
            )
        )
    ],
)
async def list_intercompany_rule_versions(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    rows = await MultiEntityConsolidationRepository(session).list_intercompany_rule_versions(
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
    "/adjustment-definitions",
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(
            consolidation_control_plane_dependency(
                action="consolidation_adjustment_manage",
                resource_type="consolidation_adjustment_definition",
            )
        )
    ],
)
async def create_adjustment_definition(
    body: ConsolidationAdjustmentCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    repository = MultiEntityConsolidationRepository(session)
    version_token = build_definition_version_token(
        DefinitionVersionTokenInput(rows=[body.model_dump(mode="json")])
    )
    try:
        row = await repository.create_adjustment_definition(
            tenant_id=user.tenant_id,
            organisation_id=body.organisation_id,
            adjustment_code=body.adjustment_code,
            adjustment_name=body.adjustment_name,
            adjustment_type=body.adjustment_type,
            logic_json=body.logic_json,
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
    return {
        "id": str(row.id),
        "adjustment_code": row.adjustment_code,
        "version_token": row.version_token,
    }


@router.get(
    "/adjustment-definitions",
    dependencies=[
        Depends(
            consolidation_control_plane_dependency(
                action="consolidation_view",
                resource_type="consolidation_adjustment_definition",
            )
        )
    ],
)
async def list_adjustment_definitions(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    rows = await MultiEntityConsolidationRepository(session).list_adjustment_definitions(
        tenant_id=user.tenant_id
    )
    return [
        {
            "id": str(row.id),
            "adjustment_code": row.adjustment_code,
            "adjustment_name": row.adjustment_name,
            "adjustment_type": row.adjustment_type,
            "version_token": row.version_token,
            "status": row.status,
        }
        for row in rows
    ]


@router.get(
    "/adjustment-definitions/{id}/versions",
    dependencies=[
        Depends(
            consolidation_control_plane_dependency(
                action="consolidation_view",
                resource_type="consolidation_adjustment_definition",
            )
        )
    ],
)
async def list_adjustment_definition_versions(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    rows = await MultiEntityConsolidationRepository(session).list_adjustment_versions(
        tenant_id=user.tenant_id,
        adjustment_id=id,
    )
    return [
        {
            "id": str(row.id),
            "adjustment_code": row.adjustment_code,
            "version_token": row.version_token,
            "status": row.status,
            "effective_from": row.effective_from.isoformat(),
        }
        for row in rows
    ]


@router.post(
    "/runs",
    response_model=ConsolidationRunCreateResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(
            consolidation_control_plane_dependency(
                action="consolidation_run",
                resource_type="multi_entity_consolidation_run",
            )
        )
    ],
)
async def create_run(
    body: ConsolidationRunCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> ConsolidationRunCreateResponse:
    service = _build_service(session)
    try:
        response = await service.create_run(
            tenant_id=user.tenant_id,
            organisation_id=body.organisation_id,
            reporting_period=body.reporting_period,
            source_run_refs=[row.model_dump(mode="json") for row in body.source_run_refs],
            created_by=user.id,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail="internal_error") from exc
    await session.flush()
    return ConsolidationRunCreateResponse(
        run_id=uuid.UUID(response["run_id"]),
        run_token=response["run_token"],
        status=response["status"],
        idempotent=bool(response["idempotent"]),
    )


@router.post(
    "/runs/{id}/execute",
    response_model=ConsolidationRunExecuteResponse,
    dependencies=[
        Depends(
            consolidation_control_plane_dependency(
                action="consolidation_run",
                resource_type="multi_entity_consolidation_run",
            )
        )
    ],
)
async def execute_run(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> ConsolidationRunExecuteResponse:
    service = _build_service(session)
    try:
        response = await service.execute_run(
            tenant_id=user.tenant_id,
            run_id=id,
            created_by=user.id,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail="internal_error") from exc
    await session.flush()
    return ConsolidationRunExecuteResponse(
        run_id=uuid.UUID(response["run_id"]),
        run_token=response["run_token"],
        status=response["status"],
        metric_count=int(response["metric_count"]),
        variance_count=int(response["variance_count"]),
        evidence_count=int(response["evidence_count"]),
        idempotent=bool(response["idempotent"]),
    )


@router.get(
    "/runs/{id}",
    dependencies=[
        Depends(
            consolidation_control_plane_dependency(
                action="consolidation_view",
                resource_type="multi_entity_consolidation_run",
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
        raise HTTPException(status_code=404, detail="Consolidation run not found")
    return row


@router.get(
    "/runs/{id}/summary",
    dependencies=[
        Depends(
            consolidation_control_plane_dependency(
                action="consolidation_view",
                resource_type="multi_entity_consolidation_run",
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
        raise HTTPException(status_code=404, detail="internal_error") from exc


@router.get(
    "/runs/{id}/metrics",
    dependencies=[
        Depends(
            consolidation_control_plane_dependency(
                action="consolidation_view",
                resource_type="multi_entity_consolidation_metric_result",
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
            consolidation_control_plane_dependency(
                action="consolidation_view",
                resource_type="multi_entity_consolidation_variance_result",
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
            consolidation_control_plane_dependency(
                action="consolidation_view",
                resource_type="risk_result",
            )
        )
    ],
)
async def list_group_risks(_: uuid.UUID) -> list[dict]:
    return []


@router.get(
    "/runs/{id}/anomalies",
    dependencies=[
        Depends(
            consolidation_control_plane_dependency(
                action="consolidation_view",
                resource_type="anomaly_result",
            )
        )
    ],
)
async def list_group_anomalies(_: uuid.UUID) -> list[dict]:
    return []


@router.get(
    "/runs/{id}/board-pack",
    dependencies=[
        Depends(
            consolidation_control_plane_dependency(
                action="consolidation_view",
                resource_type="board_pack_result",
            )
        )
    ],
)
async def get_group_board_pack(_: uuid.UUID) -> dict:
    return {"status": "not_generated", "sections": []}


@router.get(
    "/runs/{id}/evidence",
    dependencies=[
        Depends(
            consolidation_control_plane_dependency(
                action="consolidation_evidence_view",
                resource_type="multi_entity_consolidation_evidence_link",
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
