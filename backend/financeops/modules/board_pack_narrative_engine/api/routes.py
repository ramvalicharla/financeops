from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user
from financeops.db.models.users import IamUser
from financeops.modules.board_pack_narrative_engine.api.schemas import (
    BoardPackDefinitionCreateRequest,
    BoardPackRunCreateRequest,
    BoardPackRunCreateResponse,
    BoardPackRunExecuteResponse,
    BoardPackSectionCreateRequest,
    InclusionRuleCreateRequest,
    NarrativeTemplateCreateRequest,
)
from financeops.modules.board_pack_narrative_engine.application.inclusion_service import (
    InclusionService,
)
from financeops.modules.board_pack_narrative_engine.application.narrative_service import (
    NarrativeService,
)
from financeops.modules.board_pack_narrative_engine.application.run_service import RunService
from financeops.modules.board_pack_narrative_engine.application.section_service import (
    SectionService,
)
from financeops.modules.board_pack_narrative_engine.application.validation_service import (
    ValidationService,
)
from financeops.modules.board_pack_narrative_engine.domain.value_objects import (
    DefinitionVersionTokenInput,
)
from financeops.modules.board_pack_narrative_engine.infrastructure.repository import (
    BoardPackNarrativeRepository,
)
from financeops.modules.board_pack_narrative_engine.infrastructure.token_builder import (
    build_definition_version_token,
)
from financeops.modules.board_pack_narrative_engine.policies.control_plane_policy import (
    board_pack_control_plane_dependency,
)

router = APIRouter()


def _build_service(session: AsyncSession) -> RunService:
    return RunService(
        repository=BoardPackNarrativeRepository(session),
        validation_service=ValidationService(),
        inclusion_service=InclusionService(),
        section_service=SectionService(),
        narrative_service=NarrativeService(),
    )


@router.post(
    "/definitions",
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(
            board_pack_control_plane_dependency(
                action="board_pack_definition_manage",
                resource_type="board_pack_definition",
            )
        )
    ],
)
async def create_definition(
    body: BoardPackDefinitionCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    repository = BoardPackNarrativeRepository(session)
    version_token = build_definition_version_token(
        DefinitionVersionTokenInput(rows=[body.model_dump(mode="json")])
    )
    try:
        row = await repository.create_board_pack_definition(
            tenant_id=user.tenant_id,
            organisation_id=body.organisation_id,
            board_pack_code=body.board_pack_code,
            board_pack_name=body.board_pack_name,
            audience_scope=body.audience_scope,
            section_order_json=body.section_order_json,
            inclusion_config_json=body.inclusion_config_json,
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
        "board_pack_code": row.board_pack_code,
        "version_token": row.version_token,
        "status": row.status,
    }


@router.get(
    "/definitions",
    dependencies=[
        Depends(
            board_pack_control_plane_dependency(
                action="board_pack_view", resource_type="board_pack_definition"
            )
        )
    ],
)
async def list_definitions(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    rows = await BoardPackNarrativeRepository(session).list_board_pack_definitions(
        tenant_id=user.tenant_id
    )
    return [
        {
            "id": str(row.id),
            "board_pack_code": row.board_pack_code,
            "board_pack_name": row.board_pack_name,
            "audience_scope": row.audience_scope,
            "version_token": row.version_token,
            "status": row.status,
            "effective_from": row.effective_from.isoformat(),
        }
        for row in rows
    ]


@router.get(
    "/definitions/{id}/versions",
    dependencies=[
        Depends(
            board_pack_control_plane_dependency(
                action="board_pack_view", resource_type="board_pack_definition"
            )
        )
    ],
)
async def list_definition_versions(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    rows = await BoardPackNarrativeRepository(session).list_board_pack_definition_versions(
        tenant_id=user.tenant_id,
        definition_id=id,
    )
    return [
        {
            "id": str(row.id),
            "board_pack_code": row.board_pack_code,
            "version_token": row.version_token,
            "status": row.status,
            "effective_from": row.effective_from.isoformat(),
        }
        for row in rows
    ]


@router.post(
    "/sections",
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(
            board_pack_control_plane_dependency(
                action="board_pack_section_manage",
                resource_type="board_pack_section_definition",
            )
        )
    ],
)
async def create_section(
    body: BoardPackSectionCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    repository = BoardPackNarrativeRepository(session)
    version_token = build_definition_version_token(
        DefinitionVersionTokenInput(rows=[body.model_dump(mode="json")])
    )
    try:
        row = await repository.create_section_definition(
            tenant_id=user.tenant_id,
            organisation_id=body.organisation_id,
            section_code=body.section_code,
            section_name=body.section_name,
            section_type=body.section_type,
            render_logic_json=body.render_logic_json,
            section_order_default=body.section_order_default,
            narrative_template_ref=body.narrative_template_ref,
            risk_inclusion_rule_json=body.risk_inclusion_rule_json,
            anomaly_inclusion_rule_json=body.anomaly_inclusion_rule_json,
            metric_inclusion_rule_json=body.metric_inclusion_rule_json,
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
        "section_code": row.section_code,
        "version_token": row.version_token,
        "status": row.status,
    }


@router.get(
    "/sections",
    dependencies=[
        Depends(
            board_pack_control_plane_dependency(
                action="board_pack_view",
                resource_type="board_pack_section_definition",
            )
        )
    ],
)
async def list_sections(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    rows = await BoardPackNarrativeRepository(session).list_section_definitions(
        tenant_id=user.tenant_id
    )
    return [
        {
            "id": str(row.id),
            "section_code": row.section_code,
            "section_name": row.section_name,
            "section_type": row.section_type,
            "section_order_default": row.section_order_default,
            "version_token": row.version_token,
            "status": row.status,
        }
        for row in rows
    ]


@router.get(
    "/sections/{id}/versions",
    dependencies=[
        Depends(
            board_pack_control_plane_dependency(
                action="board_pack_view",
                resource_type="board_pack_section_definition",
            )
        )
    ],
)
async def list_section_versions(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    rows = await BoardPackNarrativeRepository(session).list_section_definition_versions(
        tenant_id=user.tenant_id,
        section_id=id,
    )
    return [
        {
            "id": str(row.id),
            "section_code": row.section_code,
            "version_token": row.version_token,
            "status": row.status,
            "effective_from": row.effective_from.isoformat(),
        }
        for row in rows
    ]


@router.post(
    "/narrative-templates",
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(
            board_pack_control_plane_dependency(
                action="board_pack_template_manage",
                resource_type="narrative_template",
            )
        )
    ],
)
async def create_narrative_template(
    body: NarrativeTemplateCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    repository = BoardPackNarrativeRepository(session)
    version_token = build_definition_version_token(
        DefinitionVersionTokenInput(rows=[body.model_dump(mode="json")])
    )
    try:
        row = await repository.create_narrative_template(
            tenant_id=user.tenant_id,
            organisation_id=body.organisation_id,
            template_code=body.template_code,
            template_name=body.template_name,
            template_type=body.template_type,
            template_text=body.template_text,
            template_body_json=body.template_body_json,
            placeholder_schema_json=body.placeholder_schema_json,
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
        "template_code": row.template_code,
        "version_token": row.version_token,
        "status": row.status,
    }


@router.get(
    "/narrative-templates",
    dependencies=[
        Depends(
            board_pack_control_plane_dependency(
                action="board_pack_view", resource_type="narrative_template"
            )
        )
    ],
)
async def list_narrative_templates(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    rows = await BoardPackNarrativeRepository(session).list_narrative_templates(
        tenant_id=user.tenant_id
    )
    return [
        {
            "id": str(row.id),
            "template_code": row.template_code,
            "template_name": row.template_name,
            "template_type": row.template_type,
            "version_token": row.version_token,
            "status": row.status,
        }
        for row in rows
    ]


@router.get(
    "/narrative-templates/{id}/versions",
    dependencies=[
        Depends(
            board_pack_control_plane_dependency(
                action="board_pack_view", resource_type="narrative_template"
            )
        )
    ],
)
async def list_narrative_template_versions(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    rows = await BoardPackNarrativeRepository(session).list_narrative_template_versions(
        tenant_id=user.tenant_id,
        template_id=id,
    )
    return [
        {
            "id": str(row.id),
            "template_code": row.template_code,
            "version_token": row.version_token,
            "status": row.status,
            "effective_from": row.effective_from.isoformat(),
        }
        for row in rows
    ]


@router.post(
    "/inclusion-rules",
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(
            board_pack_control_plane_dependency(
                action="board_pack_inclusion_rule_manage",
                resource_type="board_pack_inclusion_rule",
            )
        )
    ],
)
async def create_inclusion_rule(
    body: InclusionRuleCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    repository = BoardPackNarrativeRepository(session)
    version_token = build_definition_version_token(
        DefinitionVersionTokenInput(rows=[body.model_dump(mode="json")])
    )
    try:
        row = await repository.create_inclusion_rule(
            tenant_id=user.tenant_id,
            organisation_id=body.organisation_id,
            rule_code=body.rule_code,
            rule_name=body.rule_name,
            rule_type=body.rule_type,
            inclusion_logic_json=body.inclusion_logic_json,
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
        "rule_code": row.rule_code,
        "version_token": row.version_token,
        "status": row.status,
    }


@router.get(
    "/inclusion-rules",
    dependencies=[
        Depends(
            board_pack_control_plane_dependency(
                action="board_pack_view", resource_type="board_pack_inclusion_rule"
            )
        )
    ],
)
async def list_inclusion_rules(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    rows = await BoardPackNarrativeRepository(session).list_inclusion_rules(
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
    "/inclusion-rules/{id}/versions",
    dependencies=[
        Depends(
            board_pack_control_plane_dependency(
                action="board_pack_view", resource_type="board_pack_inclusion_rule"
            )
        )
    ],
)
async def list_inclusion_rule_versions(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    rows = await BoardPackNarrativeRepository(session).list_inclusion_rule_versions(
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
            board_pack_control_plane_dependency(
                action="board_pack_run", resource_type="board_pack_run"
            )
        )
    ],
    response_model=BoardPackRunCreateResponse,
)
async def create_run(
    body: BoardPackRunCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    try:
        payload = await _build_service(session).create_run(
            tenant_id=user.tenant_id,
            organisation_id=body.organisation_id,
            reporting_period=body.reporting_period,
            source_metric_run_ids=body.source_metric_run_ids,
            source_risk_run_ids=body.source_risk_run_ids,
            source_anomaly_run_ids=body.source_anomaly_run_ids,
            created_by=user.id,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await session.commit()
    return payload


@router.post(
    "/runs/{id}/execute",
    dependencies=[
        Depends(
            board_pack_control_plane_dependency(
                action="board_pack_run", resource_type="board_pack_run"
            )
        )
    ],
    response_model=BoardPackRunExecuteResponse,
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
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await session.commit()
    return payload


@router.get(
    "/runs/{id}",
    dependencies=[
        Depends(
            board_pack_control_plane_dependency(
                action="board_pack_view", resource_type="board_pack_run"
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
        raise HTTPException(status_code=404, detail="Board pack run not found")
    return row


@router.get(
    "/runs/{id}/summary",
    dependencies=[
        Depends(
            board_pack_control_plane_dependency(
                action="board_pack_view", resource_type="board_pack_result"
            )
        )
    ],
)
async def run_summary(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    try:
        return await _build_service(session).summary(tenant_id=user.tenant_id, run_id=id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/runs/{id}/sections",
    dependencies=[
        Depends(
            board_pack_control_plane_dependency(
                action="board_pack_view", resource_type="board_pack_section_result"
            )
        )
    ],
)
async def list_sections_for_run(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    return await _build_service(session).list_sections(tenant_id=user.tenant_id, run_id=id)


@router.get(
    "/runs/{id}/narratives",
    dependencies=[
        Depends(
            board_pack_control_plane_dependency(
                action="board_pack_view", resource_type="board_pack_narrative_block"
            )
        )
    ],
)
async def list_narratives_for_run(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    return await _build_service(session).list_narratives(tenant_id=user.tenant_id, run_id=id)


@router.get(
    "/runs/{id}/evidence",
    dependencies=[
        Depends(
            board_pack_control_plane_dependency(
                action="board_pack_evidence_view", resource_type="board_pack_evidence_link"
            )
        )
    ],
)
async def list_evidence_for_run(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    return await _build_service(session).list_evidence(tenant_id=user.tenant_id, run_id=id)
