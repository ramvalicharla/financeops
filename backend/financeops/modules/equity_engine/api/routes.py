from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user
from financeops.db.models.users import IamUser
from financeops.modules.equity_engine.api.schemas import (
    EquityRunCreateRequest,
    EquityRunCreateResponse,
    EquityRunExecuteResponse,
    LineDefinitionCreateRequest,
    RuleCreateRequest,
    SourceMappingCreateRequest,
    StatementDefinitionCreateRequest,
)
from financeops.modules.equity_engine.application.mapping_service import MappingService
from financeops.modules.equity_engine.application.rollforward_service import RollforwardService
from financeops.modules.equity_engine.application.run_service import RunService
from financeops.modules.equity_engine.application.validation_service import ValidationService
from financeops.modules.equity_engine.domain.value_objects import DefinitionVersionTokenInput
from financeops.modules.equity_engine.infrastructure.repository import EquityRepository
from financeops.modules.equity_engine.infrastructure.token_builder import (
    build_definition_version_token,
)
from financeops.modules.equity_engine.policies.control_plane_policy import (
    equity_control_plane_dependency,
)

router = APIRouter()


def _build_service(session: AsyncSession) -> RunService:
    return RunService(
        repository=EquityRepository(session),
        validation_service=ValidationService(),
        mapping_service=MappingService(),
        rollforward_service=RollforwardService(),
    )


@router.post(
    "/statements",
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(
            equity_control_plane_dependency(
                action="equity_definition_manage",
                resource_type="equity_statement_definition",
            )
        )
    ],
)
async def create_statement_definition(
    body: StatementDefinitionCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    repository = EquityRepository(session)
    version_token = build_definition_version_token(
        DefinitionVersionTokenInput(rows=[body.model_dump(mode="json")])
    )
    try:
        row = await repository.create_statement_definition(
            tenant_id=user.tenant_id,
            organisation_id=body.organisation_id,
            statement_code=body.statement_code,
            statement_name=body.statement_name,
            reporting_currency_basis=body.reporting_currency_basis,
            ownership_basis_flag=body.ownership_basis_flag,
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
        "statement_code": row.statement_code,
        "version_token": row.version_token,
        "status": row.status,
    }


@router.get(
    "/statements",
    dependencies=[
        Depends(
            equity_control_plane_dependency(
                action="equity_view",
                resource_type="equity_statement_definition",
            )
        )
    ],
)
async def list_statement_definitions(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    rows = await EquityRepository(session).list_statement_definitions(tenant_id=user.tenant_id)
    return [
        {
            "id": str(row.id),
            "statement_code": row.statement_code,
            "statement_name": row.statement_name,
            "reporting_currency_basis": row.reporting_currency_basis,
            "ownership_basis_flag": row.ownership_basis_flag,
            "version_token": row.version_token,
            "status": row.status,
        }
        for row in rows
    ]


@router.get(
    "/statements/{id}/versions",
    dependencies=[
        Depends(
            equity_control_plane_dependency(
                action="equity_view",
                resource_type="equity_statement_definition",
            )
        )
    ],
)
async def list_statement_definition_versions(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    rows = await EquityRepository(session).list_statement_definition_versions(
        tenant_id=user.tenant_id, definition_id=id
    )
    return [
        {
            "id": str(row.id),
            "statement_code": row.statement_code,
            "version_token": row.version_token,
            "status": row.status,
            "effective_from": row.effective_from.isoformat(),
        }
        for row in rows
    ]


@router.post(
    "/line-definitions",
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(
            equity_control_plane_dependency(
                action="equity_definition_manage",
                resource_type="equity_line_definition",
            )
        )
    ],
)
async def create_line_definition(
    body: LineDefinitionCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    repository = EquityRepository(session)
    version_token = build_definition_version_token(
        DefinitionVersionTokenInput(rows=[body.model_dump(mode="json")])
    )
    try:
        row = await repository.create_line_definition(
            tenant_id=user.tenant_id,
            organisation_id=body.organisation_id,
            statement_definition_id=body.statement_definition_id,
            line_code=body.line_code,
            line_name=body.line_name,
            line_type=body.line_type,
            presentation_order=body.presentation_order,
            rollforward_required_flag=body.rollforward_required_flag,
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
        "line_code": row.line_code,
        "version_token": row.version_token,
        "status": row.status,
    }


@router.post(
    "/source-mappings",
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(
            equity_control_plane_dependency(
                action="equity_definition_manage",
                resource_type="equity_source_mapping",
            )
        )
    ],
)
async def create_source_mapping(
    body: SourceMappingCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    repository = EquityRepository(session)
    version_token = build_definition_version_token(
        DefinitionVersionTokenInput(rows=[body.model_dump(mode="json")])
    )
    try:
        row = await repository.create_source_mapping(
            tenant_id=user.tenant_id,
            organisation_id=body.organisation_id,
            mapping_code=body.mapping_code,
            line_code=body.line_code,
            source_type=body.source_type,
            source_selector_json=body.source_selector_json,
            transformation_logic_json=body.transformation_logic_json,
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
        "status": row.status,
    }


@router.post(
    "/rules",
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(
            equity_control_plane_dependency(
                action="equity_rule_manage",
                resource_type="equity_rollforward_rule_definition",
            )
        )
    ],
)
async def create_rule(
    body: RuleCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    repository = EquityRepository(session)
    version_token = build_definition_version_token(
        DefinitionVersionTokenInput(rows=[body.model_dump(mode="json")])
    )
    try:
        row = await repository.create_rollforward_rule(
            tenant_id=user.tenant_id,
            organisation_id=body.organisation_id,
            rule_code=body.rule_code,
            rule_name=body.rule_name,
            rule_type=body.rule_type,
            source_selector_json=body.source_selector_json,
            derivation_logic_json=body.derivation_logic_json,
            fx_interaction_logic_json_nullable=body.fx_interaction_logic_json_nullable,
            ownership_interaction_logic_json_nullable=body.ownership_interaction_logic_json_nullable,
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
            equity_control_plane_dependency(
                action="equity_view",
                resource_type="equity_rollforward_rule_definition",
            )
        )
    ],
)
async def list_rules(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    rows = await EquityRepository(session).list_rollforward_rules(tenant_id=user.tenant_id)
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
            equity_control_plane_dependency(
                action="equity_view",
                resource_type="equity_rollforward_rule_definition",
            )
        )
    ],
)
async def list_rule_versions(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    rows = await EquityRepository(session).list_rollforward_rule_versions(
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
    response_model=EquityRunCreateResponse,
    dependencies=[
        Depends(
            equity_control_plane_dependency(action="equity_run", resource_type="equity_run")
        )
    ],
)
async def create_run(
    body: EquityRunCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> EquityRunCreateResponse:
    service = _build_service(session)
    try:
        response = await service.create_run(
            tenant_id=user.tenant_id,
            organisation_id=body.organisation_id,
            reporting_period=body.reporting_period,
            consolidation_run_ref_nullable=body.consolidation_run_ref_nullable,
            fx_translation_run_ref_nullable=body.fx_translation_run_ref_nullable,
            ownership_consolidation_run_ref_nullable=body.ownership_consolidation_run_ref_nullable,
            created_by=user.id,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await session.commit()
    return EquityRunCreateResponse(
        run_id=uuid.UUID(response["run_id"]),
        run_token=response["run_token"],
        status=response["status"],
        idempotent=bool(response["idempotent"]),
    )


@router.post(
    "/runs/{id}/execute",
    response_model=EquityRunExecuteResponse,
    dependencies=[
        Depends(
            equity_control_plane_dependency(action="equity_run", resource_type="equity_run")
        )
    ],
)
async def execute_run(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> EquityRunExecuteResponse:
    service = _build_service(session)
    try:
        response = await service.execute_run(
            tenant_id=user.tenant_id,
            run_id=id,
            created_by=user.id,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await session.commit()
    return EquityRunExecuteResponse(
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
            equity_control_plane_dependency(action="equity_view", resource_type="equity_run")
        )
    ],
)
async def get_run(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    run = await EquityRepository(session).get_run(tenant_id=user.tenant_id, run_id=id)
    if run is None:
        raise HTTPException(status_code=404, detail="equity run not found")
    return {
        "id": str(run.id),
        "run_token": run.run_token,
        "run_status": run.run_status,
        "reporting_period": run.reporting_period.isoformat(),
        "statement_definition_version_token": run.statement_definition_version_token,
        "line_definition_version_token": run.line_definition_version_token,
        "rollforward_rule_version_token": run.rollforward_rule_version_token,
        "source_mapping_version_token": run.source_mapping_version_token,
    }


@router.get(
    "/runs/{id}/summary",
    dependencies=[
        Depends(
            equity_control_plane_dependency(action="equity_view", resource_type="equity_run")
        )
    ],
)
async def get_run_summary(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    repo = EquityRepository(session)
    run = await repo.get_run(tenant_id=user.tenant_id, run_id=id)
    if run is None:
        raise HTTPException(status_code=404, detail="equity run not found")
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
            equity_control_plane_dependency(action="equity_view", resource_type="equity_run")
        )
    ],
)
async def get_run_lines(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    rows = await EquityRepository(session).list_line_results(tenant_id=user.tenant_id, run_id=id)
    return [
        {
            "id": str(row.id),
            "line_no": row.line_no,
            "line_code": row.line_code,
            "opening_balance": str(row.opening_balance),
            "movement_amount": str(row.movement_amount),
            "closing_balance": str(row.closing_balance),
        }
        for row in rows
    ]


@router.get(
    "/runs/{id}/statement",
    dependencies=[
        Depends(
            equity_control_plane_dependency(action="equity_view", resource_type="equity_run")
        )
    ],
)
async def get_run_statement(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    row = await EquityRepository(session).get_statement_result(tenant_id=user.tenant_id, run_id=id)
    if row is None:
        raise HTTPException(status_code=404, detail="equity statement result not found")
    return {
        "id": str(row.id),
        "total_equity_opening": str(row.total_equity_opening),
        "total_equity_closing": str(row.total_equity_closing),
        "statement_payload_json": row.statement_payload_json,
    }


@router.get(
    "/runs/{id}/evidence",
    dependencies=[
        Depends(
            equity_control_plane_dependency(action="equity_view", resource_type="equity_run")
        )
    ],
)
async def get_run_evidence(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    rows = await EquityRepository(session).list_evidence(tenant_id=user.tenant_id, run_id=id)
    return [
        {
            "id": str(row.id),
            "result_id": str(row.result_id) if row.result_id else None,
            "evidence_type": row.evidence_type,
            "evidence_ref": row.evidence_ref,
            "evidence_label": row.evidence_label,
        }
        for row in rows
    ]
