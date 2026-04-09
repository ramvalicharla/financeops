from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user
from financeops.core.intent.api import build_idempotency_key, build_intent_actor
from financeops.core.intent.enums import IntentType
from financeops.core.intent.service import IntentService
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
from financeops.platform.services.control_plane.phase4_service import Phase4ControlPlaneService

router = APIRouter()


def _build_service(session: AsyncSession) -> RunService:
    return RunService(
        repository=BoardPackNarrativeRepository(session),
        validation_service=ValidationService(),
        inclusion_service=InclusionService(),
        section_service=SectionService(),
        narrative_service=NarrativeService(),
    )


async def _submit_intent(
    request: Request,
    session: AsyncSession,
    *,
    user: IamUser,
    intent_type: IntentType,
    payload: dict,
    target_id: uuid.UUID | None = None,
):
    return await IntentService(session).submit_intent(
        intent_type=intent_type,
        actor=build_intent_actor(request, user),
        payload=payload,
        target_id=target_id,
        idempotency_key=build_idempotency_key(
            request,
            intent_type=intent_type,
            actor=user,
            body=payload,
            target_id=target_id,
        ),
    )


async def _snapshot_refs(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    subject_type: str,
    subject_id: uuid.UUID,
) -> list[str]:
    snapshots = await Phase4ControlPlaneService(session).list_subject_snapshots(
        tenant_id=tenant_id,
        subject_type=subject_type,
        subject_id=str(subject_id),
        limit=10,
    )
    return [str(row["snapshot_id"]) for row in snapshots]


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
    request: Request,
    body: BoardPackDefinitionCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    repository = BoardPackNarrativeRepository(session)
    try:
        result = await _submit_intent(
            request,
            session,
            user=user,
            intent_type=IntentType.CREATE_BOARD_PACK_NARRATIVE_DEFINITION,
            payload=body.model_dump(mode="json"),
        )
        row = await repository.get_board_pack_definition(
            tenant_id=user.tenant_id,
            definition_id=uuid.UUID(str((result.record_refs or {})["definition_id"])),
        )
        if row is None:
            raise RuntimeError("Governed board pack definition was not created")
    except Exception as exc:
        raise HTTPException(status_code=400, detail="internal_error") from exc
    await session.flush()
    return {
        "id": str(row.id),
        "board_pack_code": row.board_pack_code,
        "version_token": row.version_token,
        "status": row.status,
        "intent_id": str(result.intent_id),
        "job_id": str(result.job_id) if result.job_id is not None else None,
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
    request: Request,
    body: BoardPackSectionCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    repository = BoardPackNarrativeRepository(session)
    try:
        result = await _submit_intent(
            request,
            session,
            user=user,
            intent_type=IntentType.CREATE_BOARD_PACK_SECTION_DEFINITION,
            payload=body.model_dump(mode="json"),
        )
        row = await repository.get_section_definition(
            tenant_id=user.tenant_id,
            section_id=uuid.UUID(str((result.record_refs or {})["section_id"])),
        )
        if row is None:
            raise RuntimeError("Governed board pack section was not created")
    except Exception as exc:
        raise HTTPException(status_code=400, detail="internal_error") from exc
    await session.flush()
    return {
        "id": str(row.id),
        "section_code": row.section_code,
        "version_token": row.version_token,
        "status": row.status,
        "intent_id": str(result.intent_id),
        "job_id": str(result.job_id) if result.job_id is not None else None,
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
    request: Request,
    body: NarrativeTemplateCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    repository = BoardPackNarrativeRepository(session)
    try:
        result = await _submit_intent(
            request,
            session,
            user=user,
            intent_type=IntentType.CREATE_NARRATIVE_TEMPLATE,
            payload=body.model_dump(mode="json"),
        )
        row = await repository.get_narrative_template(
            tenant_id=user.tenant_id,
            template_id=uuid.UUID(str((result.record_refs or {})["template_id"])),
        )
        if row is None:
            raise RuntimeError("Governed narrative template was not created")
    except Exception as exc:
        raise HTTPException(status_code=400, detail="internal_error") from exc
    await session.flush()
    return {
        "id": str(row.id),
        "template_code": row.template_code,
        "version_token": row.version_token,
        "status": row.status,
        "intent_id": str(result.intent_id),
        "job_id": str(result.job_id) if result.job_id is not None else None,
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
    request: Request,
    body: InclusionRuleCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    repository = BoardPackNarrativeRepository(session)
    try:
        result = await _submit_intent(
            request,
            session,
            user=user,
            intent_type=IntentType.CREATE_BOARD_PACK_INCLUSION_RULE,
            payload=body.model_dump(mode="json"),
        )
        row = await repository.get_inclusion_rule(
            tenant_id=user.tenant_id,
            rule_id=uuid.UUID(str((result.record_refs or {})["rule_id"])),
        )
        if row is None:
            raise RuntimeError("Governed inclusion rule was not created")
    except Exception as exc:
        raise HTTPException(status_code=400, detail="internal_error") from exc
    await session.flush()
    return {
        "id": str(row.id),
        "rule_code": row.rule_code,
        "version_token": row.version_token,
        "status": row.status,
        "intent_id": str(result.intent_id),
        "job_id": str(result.job_id) if result.job_id is not None else None,
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
    request: Request,
    body: BoardPackRunCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    try:
        result = await _submit_intent(
            request,
            session,
            user=user,
            intent_type=IntentType.CREATE_BOARD_PACK_NARRATIVE_RUN,
            payload=body.model_dump(mode="json"),
        )
        run_id = uuid.UUID(str((result.record_refs or {})["run_id"]))
    except Exception as exc:
        raise HTTPException(status_code=400, detail="internal_error") from exc
    await session.flush()
    return {
        **dict(result.record_refs or {}),
        "intent_id": result.intent_id,
        "job_id": result.job_id,
        "determinism_hash": (result.record_refs or {}).get("determinism_hash"),
        "snapshot_refs": await _snapshot_refs(
            session,
            tenant_id=user.tenant_id,
            subject_type="board_pack_run",
            subject_id=run_id,
        ),
    }


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
    request: Request,
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    try:
        result = await _submit_intent(
            request,
            session,
            user=user,
            intent_type=IntentType.EXECUTE_BOARD_PACK_NARRATIVE_RUN,
            payload={},
            target_id=id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="internal_error") from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail="internal_error") from exc
    await session.flush()
    return {
        **dict(result.record_refs or {}),
        "intent_id": result.intent_id,
        "job_id": result.job_id,
        "determinism_hash": (result.record_refs or {}).get("determinism_hash"),
        "snapshot_refs": await _snapshot_refs(
            session,
            tenant_id=user.tenant_id,
            subject_type="board_pack_run",
            subject_id=id,
        ),
    }


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
        raise HTTPException(status_code=404, detail="internal_error") from exc


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
