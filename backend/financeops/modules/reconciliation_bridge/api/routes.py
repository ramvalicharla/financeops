from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user
from financeops.db.models.users import IamUser
from financeops.modules.reconciliation_bridge.api.schemas import (
    ReconciliationActionResponse,
    ReconciliationAttachEvidenceRequest,
    ReconciliationLineExplainRequest,
    ReconciliationSessionCreateRequest,
    ReconciliationSessionCreateResponse,
    ReconciliationSessionRunResponse,
    ReconciliationSessionSummaryResponse,
)
from financeops.modules.reconciliation_bridge.application.exception_classification_service import (
    ExceptionClassificationService,
)
from financeops.modules.reconciliation_bridge.application.matching_service import (
    MatchingService,
)
from financeops.modules.reconciliation_bridge.application.run_service import (
    ReconciliationRunService,
)
from financeops.modules.reconciliation_bridge.infrastructure.repository import (
    ReconciliationBridgeRepository,
)
from financeops.modules.reconciliation_bridge.policies.control_plane_policy import (
    reconciliation_control_plane_dependency,
)

router = APIRouter()


def _build_service(session: AsyncSession) -> ReconciliationRunService:
    return ReconciliationRunService(
        repository=ReconciliationBridgeRepository(session),
        matching_service=MatchingService(),
        exception_classification_service=ExceptionClassificationService(),
    )


@router.post(
    "/sessions",
    response_model=ReconciliationSessionCreateResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(
            reconciliation_control_plane_dependency(
                action="reconciliation_session_create",
                resource_type="reconciliation_session",
            )
        )
    ],
)
async def create_reconciliation_session(
    body: ReconciliationSessionCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> ReconciliationSessionCreateResponse:
    service = _build_service(session)
    try:
        result = await service.create_session(
            tenant_id=user.tenant_id,
            organisation_id=body.organisation_id,
            reconciliation_type=body.reconciliation_type,
            source_a_type=body.source_a_type,
            source_a_ref=body.source_a_ref,
            source_b_type=body.source_b_type,
            source_b_ref=body.source_b_ref,
            period_start=body.period_start,
            period_end=body.period_end,
            matching_rule_version=body.matching_rule_version,
            tolerance_rule_version=body.tolerance_rule_version,
            materiality_config_json=body.materiality_config_json,
            created_by=user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await session.commit()
    return ReconciliationSessionCreateResponse(**result)


@router.post(
    "/sessions/{id}/run",
    response_model=ReconciliationSessionRunResponse,
    dependencies=[
        Depends(
            reconciliation_control_plane_dependency(
                action="reconciliation_run",
                resource_type="reconciliation_session",
            )
        )
    ],
)
async def run_reconciliation_session(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> ReconciliationSessionRunResponse:
    service = _build_service(session)
    try:
        result = await service.run_session(
            tenant_id=user.tenant_id,
            session_id=id,
            actor_user_id=user.id,
        )
    except ValueError as exc:
        detail = str(exc)
        raise HTTPException(
            status_code=404 if "not found" in detail.lower() else 400,
            detail=detail,
        ) from exc
    await session.commit()
    return ReconciliationSessionRunResponse(**result)


@router.get(
    "/sessions/{id}",
    dependencies=[
        Depends(
            reconciliation_control_plane_dependency(
                action="reconciliation_view",
                resource_type="reconciliation_session",
            )
        )
    ],
)
async def get_reconciliation_session(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    service = _build_service(session)
    row = await service.get_session(tenant_id=user.tenant_id, session_id=id)
    if row is None:
        raise HTTPException(status_code=404, detail="Reconciliation session not found")
    return row


@router.get(
    "/sessions/{id}/summary",
    response_model=ReconciliationSessionSummaryResponse,
    dependencies=[
        Depends(
            reconciliation_control_plane_dependency(
                action="reconciliation_view",
                resource_type="reconciliation_session",
            )
        )
    ],
)
async def get_reconciliation_session_summary(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> ReconciliationSessionSummaryResponse:
    service = _build_service(session)
    summary = await service.get_summary(tenant_id=user.tenant_id, session_id=id)
    return ReconciliationSessionSummaryResponse(**summary)


@router.get(
    "/sessions/{id}/lines",
    dependencies=[
        Depends(
            reconciliation_control_plane_dependency(
                action="reconciliation_view",
                resource_type="reconciliation_line",
            )
        )
    ],
)
async def list_reconciliation_lines(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    service = _build_service(session)
    return await service.list_lines(tenant_id=user.tenant_id, session_id=id)


@router.get(
    "/sessions/{id}/exceptions",
    dependencies=[
        Depends(
            reconciliation_control_plane_dependency(
                action="reconciliation_view",
                resource_type="reconciliation_exception",
            )
        )
    ],
)
async def list_reconciliation_exceptions(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    service = _build_service(session)
    return await service.list_exceptions(tenant_id=user.tenant_id, session_id=id)


@router.post(
    "/lines/{id}/explain",
    response_model=ReconciliationActionResponse,
    dependencies=[
        Depends(
            reconciliation_control_plane_dependency(
                action="reconciliation_review",
                resource_type="reconciliation_line",
            )
        )
    ],
)
async def add_reconciliation_line_explanation(
    id: uuid.UUID,
    body: ReconciliationLineExplainRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> ReconciliationActionResponse:
    service = _build_service(session)
    try:
        result = await service.add_explanation(
            tenant_id=user.tenant_id,
            line_id=id,
            explanation=body.explanation,
            actor_user_id=user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await session.commit()
    return ReconciliationActionResponse(event_id=uuid.UUID(result["event_id"]))


@router.post(
    "/lines/{id}/attach-evidence",
    response_model=ReconciliationActionResponse,
    dependencies=[
        Depends(
            reconciliation_control_plane_dependency(
                action="reconciliation_evidence_attach",
                resource_type="reconciliation_evidence_link",
            )
        )
    ],
)
async def attach_reconciliation_line_evidence(
    id: uuid.UUID,
    body: ReconciliationAttachEvidenceRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> ReconciliationActionResponse:
    service = _build_service(session)
    try:
        result = await service.attach_evidence(
            tenant_id=user.tenant_id,
            line_id=id,
            evidence_type=body.evidence_type,
            evidence_ref=body.evidence_ref,
            evidence_label=body.evidence_label,
            actor_user_id=user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await session.commit()
    return ReconciliationActionResponse(evidence_id=uuid.UUID(result["evidence_id"]))


@router.post(
    "/lines/{id}/resolve",
    response_model=ReconciliationActionResponse,
    dependencies=[
        Depends(
            reconciliation_control_plane_dependency(
                action="reconciliation_exception_resolve",
                resource_type="reconciliation_exception",
            )
        )
    ],
)
async def resolve_reconciliation_line(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> ReconciliationActionResponse:
    service = _build_service(session)
    try:
        result = await service.resolve_line(
            tenant_id=user.tenant_id,
            line_id=id,
            actor_user_id=user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await session.commit()
    return ReconciliationActionResponse(
        exception_id=uuid.UUID(result["exception_id"]),
        event_id=uuid.UUID(result["event_id"]),
    )


@router.post(
    "/lines/{id}/reopen",
    response_model=ReconciliationActionResponse,
    dependencies=[
        Depends(
            reconciliation_control_plane_dependency(
                action="reconciliation_exception_resolve",
                resource_type="reconciliation_exception",
            )
        )
    ],
)
async def reopen_reconciliation_line(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> ReconciliationActionResponse:
    service = _build_service(session)
    try:
        result = await service.reopen_line(
            tenant_id=user.tenant_id,
            line_id=id,
            actor_user_id=user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await session.commit()
    return ReconciliationActionResponse(
        exception_id=uuid.UUID(result["exception_id"]),
        event_id=uuid.UUID(result["event_id"]),
    )
