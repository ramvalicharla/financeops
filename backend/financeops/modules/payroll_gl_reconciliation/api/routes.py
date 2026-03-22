from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user
from financeops.db.models.users import IamUser
from financeops.modules.payroll_gl_reconciliation.api.schemas import (
    ActionResponse,
    AttachEvidenceRequest,
    MappingCreateRequest,
    RuleCreateRequest,
    RunCreateRequest,
    RunCreateResponse,
    RunExecuteResponse,
    RunSummaryResponse,
)
from financeops.modules.payroll_gl_reconciliation.application.classification_service import (
    ClassificationService,
)
from financeops.modules.payroll_gl_reconciliation.application.mapping_service import (
    MappingService,
)
from financeops.modules.payroll_gl_reconciliation.application.matching_service import (
    MatchingService,
)
from financeops.modules.payroll_gl_reconciliation.application.rule_service import RuleService
from financeops.modules.payroll_gl_reconciliation.application.run_service import (
    PayrollGlReconciliationRunService,
)
from financeops.modules.payroll_gl_reconciliation.application.validation_service import (
    ValidationService,
)
from financeops.modules.payroll_gl_reconciliation.infrastructure.repository import (
    PayrollGlReconciliationRepository,
)
from financeops.modules.payroll_gl_reconciliation.policies.control_plane_policy import (
    payroll_gl_reconciliation_control_plane_dependency,
)

router = APIRouter()


def _build_run_service(session: AsyncSession) -> PayrollGlReconciliationRunService:
    return PayrollGlReconciliationRunService(
        repository=PayrollGlReconciliationRepository(session),
        mapping_service=MappingService(),
        rule_service=RuleService(),
        matching_service=MatchingService(),
        classification_service=ClassificationService(),
        validation_service=ValidationService(),
    )


@router.post(
    "/mappings",
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(
            payroll_gl_reconciliation_control_plane_dependency(
                action="payroll_gl_reconciliation_mapping_manage",
                resource_type="payroll_gl_reconciliation_mapping",
            )
        )
    ],
)
async def create_mapping(
    body: MappingCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    repository = PayrollGlReconciliationRepository(session)
    try:
        row = await repository.create_mapping(
            tenant_id=user.tenant_id,
            organisation_id=body.organisation_id,
            mapping_code=body.mapping_code,
            mapping_name=body.mapping_name,
            payroll_metric_code=body.payroll_metric_code,
            gl_account_selector_json=body.gl_account_selector_json,
            cost_center_rule_json=body.cost_center_rule_json,
            department_rule_json=body.department_rule_json,
            entity_rule_json=body.entity_rule_json,
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
        "mapping_code": row.mapping_code,
        "status": row.status,
        "effective_from": row.effective_from.isoformat(),
    }


@router.get(
    "/mappings",
    dependencies=[
        Depends(
            payroll_gl_reconciliation_control_plane_dependency(
                action="payroll_gl_reconciliation_view",
                resource_type="payroll_gl_reconciliation_mapping",
            )
        )
    ],
)
async def list_mappings(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    repository = PayrollGlReconciliationRepository(session)
    rows = await repository.list_mappings(tenant_id=user.tenant_id)
    return [
        {
            "id": str(row.id),
            "organisation_id": str(row.organisation_id),
            "mapping_code": row.mapping_code,
            "mapping_name": row.mapping_name,
            "payroll_metric_code": row.payroll_metric_code,
            "status": row.status,
            "effective_from": row.effective_from.isoformat(),
            "supersedes_id": str(row.supersedes_id) if row.supersedes_id else None,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]


@router.get(
    "/mappings/{id}/versions",
    dependencies=[
        Depends(
            payroll_gl_reconciliation_control_plane_dependency(
                action="payroll_gl_reconciliation_view",
                resource_type="payroll_gl_reconciliation_mapping",
            )
        )
    ],
)
async def list_mapping_versions(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    repository = PayrollGlReconciliationRepository(session)
    rows = await repository.list_mapping_versions(tenant_id=user.tenant_id, mapping_id=id)
    return [
        {
            "id": str(row.id),
            "mapping_code": row.mapping_code,
            "mapping_name": row.mapping_name,
            "payroll_metric_code": row.payroll_metric_code,
            "status": row.status,
            "effective_from": row.effective_from.isoformat(),
            "supersedes_id": str(row.supersedes_id) if row.supersedes_id else None,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]


@router.post(
    "/rules",
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(
            payroll_gl_reconciliation_control_plane_dependency(
                action="payroll_gl_reconciliation_rule_manage",
                resource_type="payroll_gl_reconciliation_rule",
            )
        )
    ],
)
async def create_rule(
    body: RuleCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    repository = PayrollGlReconciliationRepository(session)
    try:
        row = await repository.create_rule(
            tenant_id=user.tenant_id,
            organisation_id=body.organisation_id,
            rule_code=body.rule_code,
            rule_name=body.rule_name,
            rule_type=body.rule_type,
            tolerance_json=body.tolerance_json,
            materiality_json=body.materiality_json,
            timing_window_json=body.timing_window_json,
            classification_behavior_json=body.classification_behavior_json,
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
        "status": row.status,
        "effective_from": row.effective_from.isoformat(),
    }


@router.get(
    "/rules",
    dependencies=[
        Depends(
            payroll_gl_reconciliation_control_plane_dependency(
                action="payroll_gl_reconciliation_view",
                resource_type="payroll_gl_reconciliation_rule",
            )
        )
    ],
)
async def list_rules(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    repository = PayrollGlReconciliationRepository(session)
    rows = await repository.list_rules(tenant_id=user.tenant_id)
    return [
        {
            "id": str(row.id),
            "organisation_id": str(row.organisation_id),
            "rule_code": row.rule_code,
            "rule_name": row.rule_name,
            "rule_type": row.rule_type,
            "status": row.status,
            "effective_from": row.effective_from.isoformat(),
            "supersedes_id": str(row.supersedes_id) if row.supersedes_id else None,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]


@router.get(
    "/rules/{id}/versions",
    dependencies=[
        Depends(
            payroll_gl_reconciliation_control_plane_dependency(
                action="payroll_gl_reconciliation_view",
                resource_type="payroll_gl_reconciliation_rule",
            )
        )
    ],
)
async def list_rule_versions(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    repository = PayrollGlReconciliationRepository(session)
    rows = await repository.list_rule_versions(tenant_id=user.tenant_id, rule_id=id)
    return [
        {
            "id": str(row.id),
            "rule_code": row.rule_code,
            "rule_name": row.rule_name,
            "rule_type": row.rule_type,
            "status": row.status,
            "effective_from": row.effective_from.isoformat(),
            "supersedes_id": str(row.supersedes_id) if row.supersedes_id else None,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]


@router.post(
    "/runs",
    response_model=RunCreateResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(
            payroll_gl_reconciliation_control_plane_dependency(
                action="payroll_gl_reconciliation_run",
                resource_type="payroll_gl_reconciliation_run",
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
            payroll_run_id=body.payroll_run_id,
            gl_run_id=body.gl_run_id,
            reporting_period=body.reporting_period,
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
            payroll_gl_reconciliation_control_plane_dependency(
                action="payroll_gl_reconciliation_run",
                resource_type="payroll_gl_reconciliation_run",
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
            tenant_id=user.tenant_id, run_id=id, actor_user_id=user.id
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
            payroll_gl_reconciliation_control_plane_dependency(
                action="payroll_gl_reconciliation_view",
                resource_type="payroll_gl_reconciliation_run",
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
        raise HTTPException(status_code=404, detail="Payroll-GL reconciliation run not found")
    return row


@router.get(
    "/runs/{id}/summary",
    response_model=RunSummaryResponse,
    dependencies=[
        Depends(
            payroll_gl_reconciliation_control_plane_dependency(
                action="payroll_gl_reconciliation_view",
                resource_type="payroll_gl_reconciliation_run",
            )
        )
    ],
)
async def get_run_summary(
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
    "/runs/{id}/lines",
    dependencies=[
        Depends(
            payroll_gl_reconciliation_control_plane_dependency(
                action="payroll_gl_reconciliation_view",
                resource_type="reconciliation_line",
            )
        )
    ],
)
async def list_lines(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    service = _build_run_service(session)
    try:
        return await service.list_lines(tenant_id=user.tenant_id, run_id=id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="internal_error") from exc


@router.get(
    "/runs/{id}/exceptions",
    dependencies=[
        Depends(
            payroll_gl_reconciliation_control_plane_dependency(
                action="payroll_gl_reconciliation_view",
                resource_type="reconciliation_exception",
            )
        )
    ],
)
async def list_exceptions(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    service = _build_run_service(session)
    try:
        return await service.list_exceptions(tenant_id=user.tenant_id, run_id=id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="internal_error") from exc


@router.post(
    "/lines/{id}/attach-evidence",
    response_model=ActionResponse,
    dependencies=[
        Depends(
            payroll_gl_reconciliation_control_plane_dependency(
                action="payroll_gl_reconciliation_evidence_attach",
                resource_type="reconciliation_evidence_link",
            )
        )
    ],
)
async def attach_evidence(
    id: uuid.UUID,
    body: AttachEvidenceRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> ActionResponse:
    service = _build_run_service(session)
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
        raise HTTPException(status_code=404, detail="internal_error") from exc
    await session.flush()
    return ActionResponse(
        evidence_id=uuid.UUID(result["evidence_id"]),
        event_id=uuid.UUID(result["event_id"]),
    )


@router.post(
    "/lines/{id}/resolve",
    response_model=ActionResponse,
    dependencies=[
        Depends(
            payroll_gl_reconciliation_control_plane_dependency(
                action="payroll_gl_reconciliation_exception_resolve",
                resource_type="reconciliation_exception",
            )
        )
    ],
)
async def resolve_line(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> ActionResponse:
    service = _build_run_service(session)
    try:
        result = await service.resolve_line(
            tenant_id=user.tenant_id,
            line_id=id,
            actor_user_id=user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="internal_error") from exc
    await session.flush()
    return ActionResponse(
        exception_id=uuid.UUID(result["exception_id"]),
        event_id=uuid.UUID(result["event_id"]),
    )


@router.post(
    "/lines/{id}/reopen",
    response_model=ActionResponse,
    dependencies=[
        Depends(
            payroll_gl_reconciliation_control_plane_dependency(
                action="payroll_gl_reconciliation_exception_resolve",
                resource_type="reconciliation_exception",
            )
        )
    ],
)
async def reopen_line(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> ActionResponse:
    service = _build_run_service(session)
    try:
        result = await service.reopen_line(
            tenant_id=user.tenant_id,
            line_id=id,
            actor_user_id=user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="internal_error") from exc
    await session.flush()
    return ActionResponse(
        exception_id=uuid.UUID(result["exception_id"]),
        event_id=uuid.UUID(result["event_id"]),
    )

