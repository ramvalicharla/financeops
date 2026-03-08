from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user
from financeops.db.models.users import IamUser
from financeops.modules.cash_flow_engine.api.schemas import (
    BridgeRuleCreateRequest,
    CashFlowRunCreateRequest,
    CashFlowRunCreateResponse,
    CashFlowRunExecuteResponse,
    LineMappingCreateRequest,
    StatementDefinitionCreateRequest,
)
from financeops.modules.cash_flow_engine.application.bridge_service import BridgeService
from financeops.modules.cash_flow_engine.application.mapping_service import MappingService
from financeops.modules.cash_flow_engine.application.run_service import RunService
from financeops.modules.cash_flow_engine.application.validation_service import ValidationService
from financeops.modules.cash_flow_engine.domain.value_objects import DefinitionVersionTokenInput
from financeops.modules.cash_flow_engine.infrastructure.repository import CashFlowRepository
from financeops.modules.cash_flow_engine.infrastructure.token_builder import (
    build_definition_version_token,
)
from financeops.modules.cash_flow_engine.policies.control_plane_policy import (
    cash_flow_control_plane_dependency,
)

router = APIRouter()


def _build_service(session: AsyncSession) -> RunService:
    return RunService(
        repository=CashFlowRepository(session),
        validation_service=ValidationService(),
        mapping_service=MappingService(),
        bridge_service=BridgeService(),
    )


@router.post(
    "/definitions",
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(
            cash_flow_control_plane_dependency(
                action="cash_flow_definition_manage",
                resource_type="cash_flow_statement_definition",
            )
        )
    ],
)
async def create_statement_definition(
    body: StatementDefinitionCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    repository = CashFlowRepository(session)
    version_token = build_definition_version_token(
        DefinitionVersionTokenInput(rows=[body.model_dump(mode="json")])
    )
    try:
        row = await repository.create_statement_definition(
            tenant_id=user.tenant_id,
            organisation_id=body.organisation_id,
            definition_code=body.definition_code,
            definition_name=body.definition_name,
            method_type=body.method_type,
            layout_json=body.layout_json,
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
        "definition_code": row.definition_code,
        "version_token": row.version_token,
        "status": row.status,
    }


@router.get(
    "/definitions",
    dependencies=[
        Depends(
            cash_flow_control_plane_dependency(
                action="cash_flow_view",
                resource_type="cash_flow_statement_definition",
            )
        )
    ],
)
async def list_statement_definitions(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    rows = await CashFlowRepository(session).list_statement_definitions(tenant_id=user.tenant_id)
    return [
        {
            "id": str(row.id),
            "definition_code": row.definition_code,
            "definition_name": row.definition_name,
            "method_type": row.method_type,
            "version_token": row.version_token,
            "status": row.status,
        }
        for row in rows
    ]


@router.get(
    "/definitions/{id}/versions",
    dependencies=[
        Depends(
            cash_flow_control_plane_dependency(
                action="cash_flow_view",
                resource_type="cash_flow_statement_definition",
            )
        )
    ],
)
async def list_statement_definition_versions(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    rows = await CashFlowRepository(session).list_statement_definition_versions(
        tenant_id=user.tenant_id, definition_id=id
    )
    return [
        {
            "id": str(row.id),
            "definition_code": row.definition_code,
            "version_token": row.version_token,
            "status": row.status,
            "effective_from": row.effective_from.isoformat(),
        }
        for row in rows
    ]


@router.post(
    "/line-mappings",
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(
            cash_flow_control_plane_dependency(
                action="cash_flow_mapping_manage",
                resource_type="cash_flow_line_mapping",
            )
        )
    ],
)
async def create_line_mapping(
    body: LineMappingCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    repository = CashFlowRepository(session)
    version_token = build_definition_version_token(
        DefinitionVersionTokenInput(rows=[body.model_dump(mode="json")])
    )
    try:
        row = await repository.create_line_mapping(
            tenant_id=user.tenant_id,
            organisation_id=body.organisation_id,
            mapping_code=body.mapping_code,
            line_code=body.line_code,
            line_name=body.line_name,
            section_code=body.section_code,
            line_order=body.line_order,
            method_type=body.method_type,
            source_metric_code=body.source_metric_code,
            sign_multiplier=body.sign_multiplier,
            aggregation_type=body.aggregation_type,
            ownership_applicability=body.ownership_applicability,
            fx_applicability=body.fx_applicability,
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
        "mapping_code": row.mapping_code,
        "line_code": row.line_code,
        "version_token": row.version_token,
    }


@router.get(
    "/line-mappings",
    dependencies=[
        Depends(
            cash_flow_control_plane_dependency(
                action="cash_flow_view",
                resource_type="cash_flow_line_mapping",
            )
        )
    ],
)
async def list_line_mappings(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    rows = await CashFlowRepository(session).list_line_mappings(tenant_id=user.tenant_id)
    return [
        {
            "id": str(row.id),
            "mapping_code": row.mapping_code,
            "line_code": row.line_code,
            "line_name": row.line_name,
            "line_order": row.line_order,
            "source_metric_code": row.source_metric_code,
            "version_token": row.version_token,
            "status": row.status,
        }
        for row in rows
    ]


@router.get(
    "/line-mappings/{id}/versions",
    dependencies=[
        Depends(
            cash_flow_control_plane_dependency(
                action="cash_flow_view",
                resource_type="cash_flow_line_mapping",
            )
        )
    ],
)
async def list_line_mapping_versions(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    rows = await CashFlowRepository(session).list_line_mapping_versions(
        tenant_id=user.tenant_id, mapping_id=id
    )
    return [
        {
            "id": str(row.id),
            "mapping_code": row.mapping_code,
            "line_code": row.line_code,
            "version_token": row.version_token,
            "status": row.status,
            "effective_from": row.effective_from.isoformat(),
        }
        for row in rows
    ]


@router.post(
    "/bridge-rules",
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(
            cash_flow_control_plane_dependency(
                action="cash_flow_bridge_rule_manage",
                resource_type="cash_flow_bridge_rule_definition",
            )
        )
    ],
)
async def create_bridge_rule(
    body: BridgeRuleCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    repository = CashFlowRepository(session)
    version_token = build_definition_version_token(
        DefinitionVersionTokenInput(rows=[body.model_dump(mode="json")])
    )
    try:
        row = await repository.create_bridge_rule(
            tenant_id=user.tenant_id,
            organisation_id=body.organisation_id,
            rule_code=body.rule_code,
            rule_name=body.rule_name,
            bridge_logic_json=body.bridge_logic_json,
            ownership_logic_json=body.ownership_logic_json,
            fx_logic_json=body.fx_logic_json,
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
    "/bridge-rules",
    dependencies=[
        Depends(
            cash_flow_control_plane_dependency(
                action="cash_flow_view",
                resource_type="cash_flow_bridge_rule_definition",
            )
        )
    ],
)
async def list_bridge_rules(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    rows = await CashFlowRepository(session).list_bridge_rules(tenant_id=user.tenant_id)
    return [
        {
            "id": str(row.id),
            "rule_code": row.rule_code,
            "rule_name": row.rule_name,
            "version_token": row.version_token,
            "status": row.status,
        }
        for row in rows
    ]


@router.get(
    "/bridge-rules/{id}/versions",
    dependencies=[
        Depends(
            cash_flow_control_plane_dependency(
                action="cash_flow_view",
                resource_type="cash_flow_bridge_rule_definition",
            )
        )
    ],
)
async def list_bridge_rule_versions(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    rows = await CashFlowRepository(session).list_bridge_rule_versions(
        tenant_id=user.tenant_id, rule_id=id
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
    response_model=CashFlowRunCreateResponse,
    dependencies=[
        Depends(
            cash_flow_control_plane_dependency(
                action="cash_flow_run", resource_type="cash_flow_run"
            )
        )
    ],
)
async def create_run(
    body: CashFlowRunCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> CashFlowRunCreateResponse:
    service = _build_service(session)
    try:
        response = await service.create_run(
            tenant_id=user.tenant_id,
            organisation_id=body.organisation_id,
            reporting_period=body.reporting_period,
            source_consolidation_run_ref=body.source_consolidation_run_ref,
            source_fx_translation_run_ref_nullable=body.source_fx_translation_run_ref_nullable,
            source_ownership_consolidation_run_ref_nullable=body.source_ownership_consolidation_run_ref_nullable,
            created_by=user.id,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await session.commit()
    return CashFlowRunCreateResponse(
        run_id=uuid.UUID(response["run_id"]),
        run_token=response["run_token"],
        status=response["status"],
        idempotent=bool(response["idempotent"]),
    )


@router.post(
    "/runs/{id}/execute",
    response_model=CashFlowRunExecuteResponse,
    dependencies=[
        Depends(
            cash_flow_control_plane_dependency(
                action="cash_flow_run", resource_type="cash_flow_run"
            )
        )
    ],
)
async def execute_run(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> CashFlowRunExecuteResponse:
    service = _build_service(session)
    try:
        response = await service.execute_run(
            tenant_id=user.tenant_id, run_id=id, created_by=user.id
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await session.commit()
    return CashFlowRunExecuteResponse(
        run_id=uuid.UUID(response["run_id"]),
        run_token=response["run_token"],
        status=response["status"],
        line_count=int(response["line_count"]),
        evidence_count=int(response["evidence_count"]),
        idempotent=bool(response["idempotent"]),
    )


@router.get(
    "/runs/{id}",
    dependencies=[
        Depends(
            cash_flow_control_plane_dependency(
                action="cash_flow_view", resource_type="cash_flow_run"
            )
        )
    ],
)
async def get_run(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    run = await CashFlowRepository(session).get_run(tenant_id=user.tenant_id, run_id=id)
    if run is None:
        raise HTTPException(status_code=404, detail="cash flow run not found")
    return {
        "id": str(run.id),
        "run_token": run.run_token,
        "run_status": run.run_status,
        "reporting_period": run.reporting_period.isoformat(),
        "statement_definition_version_token": run.statement_definition_version_token,
        "line_mapping_version_token": run.line_mapping_version_token,
        "bridge_rule_version_token": run.bridge_rule_version_token,
    }


@router.get(
    "/runs/{id}/summary",
    dependencies=[
        Depends(
            cash_flow_control_plane_dependency(
                action="cash_flow_view", resource_type="cash_flow_run"
            )
        )
    ],
)
async def get_run_summary(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    repo = CashFlowRepository(session)
    run = await repo.get_run(tenant_id=user.tenant_id, run_id=id)
    if run is None:
        raise HTTPException(status_code=404, detail="cash flow run not found")
    summary = await repo.summarize_run(tenant_id=user.tenant_id, run_id=id)
    return {
        "run_id": str(run.id),
        "run_token": run.run_token,
        "run_status": run.run_status,
        **summary,
    }


@router.get(
    "/runs/{id}/lines",
    dependencies=[
        Depends(
            cash_flow_control_plane_dependency(
                action="cash_flow_view", resource_type="cash_flow_run"
            )
        )
    ],
)
async def get_run_lines(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    rows = await CashFlowRepository(session).list_line_results(
        tenant_id=user.tenant_id, run_id=id
    )
    return [
        {
            "id": str(row.id),
            "line_no": row.line_no,
            "line_code": row.line_code,
            "line_name": row.line_name,
            "section_code": row.section_code,
            "line_order": row.line_order,
            "source_metric_code": row.source_metric_code,
            "source_value": str(row.source_value),
            "computed_value": str(row.computed_value),
            "currency_code": row.currency_code,
        }
        for row in rows
    ]


@router.get(
    "/runs/{id}/evidence",
    dependencies=[
        Depends(
            cash_flow_control_plane_dependency(
                action="cash_flow_evidence_view",
                resource_type="cash_flow_evidence_link",
            )
        )
    ],
)
async def get_run_evidence(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    rows = await CashFlowRepository(session).list_evidence(tenant_id=user.tenant_id, run_id=id)
    return [
        {
            "id": str(row.id),
            "line_result_id": str(row.line_result_id) if row.line_result_id else None,
            "evidence_type": row.evidence_type,
            "evidence_ref": row.evidence_ref,
            "evidence_label": row.evidence_label,
        }
        for row in rows
    ]
