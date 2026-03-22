from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user
from financeops.db.models.users import IamUser
from financeops.modules.fx_translation_reporting.api.schemas import (
    FxRatePolicyCreateRequest,
    FxTranslationRuleCreateRequest,
    FxTranslationRunCreateRequest,
    FxTranslationRunCreateResponse,
    FxTranslationRunExecuteResponse,
    ReportingCurrencyCreateRequest,
)
from financeops.modules.fx_translation_reporting.application.rate_selection_service import (
    RateSelectionService,
)
from financeops.modules.fx_translation_reporting.application.run_service import RunService
from financeops.modules.fx_translation_reporting.application.validation_service import (
    ValidationService,
)
from financeops.modules.fx_translation_reporting.domain.value_objects import (
    DefinitionVersionTokenInput,
)
from financeops.modules.fx_translation_reporting.infrastructure.repository import (
    FxTranslationReportingRepository,
)
from financeops.modules.fx_translation_reporting.infrastructure.token_builder import (
    build_definition_version_token,
)
from financeops.modules.fx_translation_reporting.policies.control_plane_policy import (
    fx_translation_control_plane_dependency,
)

router = APIRouter()


def _build_service(session: AsyncSession) -> RunService:
    return RunService(
        repository=FxTranslationReportingRepository(session),
        validation_service=ValidationService(),
        rate_selection_service=RateSelectionService(),
    )


@router.post(
    "/reporting-currencies",
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(
            fx_translation_control_plane_dependency(
                action="reporting_currency_manage",
                resource_type="reporting_currency_definition",
            )
        )
    ],
)
async def create_reporting_currency_definition(
    body: ReportingCurrencyCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    repository = FxTranslationReportingRepository(session)
    payload = body.model_dump(mode="json")
    payload["reporting_currency_code"] = payload["reporting_currency_code"].upper()
    version_token = build_definition_version_token(DefinitionVersionTokenInput(rows=[payload]))
    try:
        row = await repository.create_reporting_currency_definition(
            tenant_id=user.tenant_id,
            organisation_id=body.organisation_id,
            reporting_currency_code=body.reporting_currency_code.upper(),
            reporting_currency_name=body.reporting_currency_name,
            reporting_scope_type=body.reporting_scope_type,
            reporting_scope_ref=body.reporting_scope_ref,
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
        "reporting_currency_code": row.reporting_currency_code,
        "version_token": row.version_token,
        "status": row.status,
    }


@router.get(
    "/reporting-currencies",
    dependencies=[
        Depends(
            fx_translation_control_plane_dependency(
                action="fx_translation_view",
                resource_type="reporting_currency_definition",
            )
        )
    ],
)
async def list_reporting_currency_definitions(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    rows = await FxTranslationReportingRepository(session).list_reporting_currency_definitions(
        tenant_id=user.tenant_id
    )
    return [
        {
            "id": str(row.id),
            "reporting_currency_code": row.reporting_currency_code,
            "reporting_currency_name": row.reporting_currency_name,
            "reporting_scope_type": row.reporting_scope_type,
            "reporting_scope_ref": row.reporting_scope_ref,
            "version_token": row.version_token,
            "status": row.status,
        }
        for row in rows
    ]


@router.get(
    "/reporting-currencies/{id}/versions",
    dependencies=[
        Depends(
            fx_translation_control_plane_dependency(
                action="fx_translation_view",
                resource_type="reporting_currency_definition",
            )
        )
    ],
)
async def list_reporting_currency_definition_versions(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    rows = await FxTranslationReportingRepository(session).list_reporting_currency_versions(
        tenant_id=user.tenant_id, definition_id=id
    )
    return [
        {
            "id": str(row.id),
            "reporting_currency_code": row.reporting_currency_code,
            "version_token": row.version_token,
            "status": row.status,
            "effective_from": row.effective_from.isoformat(),
        }
        for row in rows
    ]


@router.post(
    "/translation-rules",
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(
            fx_translation_control_plane_dependency(
                action="fx_translation_rule_manage",
                resource_type="fx_translation_rule_definition",
            )
        )
    ],
)
async def create_translation_rule_definition(
    body: FxTranslationRuleCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    repository = FxTranslationReportingRepository(session)
    payload = body.model_dump(mode="json")
    payload["target_reporting_currency_code"] = payload["target_reporting_currency_code"].upper()
    version_token = build_definition_version_token(DefinitionVersionTokenInput(rows=[payload]))
    try:
        row = await repository.create_translation_rule_definition(
            tenant_id=user.tenant_id,
            organisation_id=body.organisation_id,
            rule_code=body.rule_code,
            rule_name=body.rule_name,
            translation_scope_type=body.translation_scope_type,
            translation_scope_ref=body.translation_scope_ref,
            source_currency_selector_json=body.source_currency_selector_json,
            target_reporting_currency_code=body.target_reporting_currency_code.upper(),
            rule_logic_json=body.rule_logic_json,
            rate_policy_ref=body.rate_policy_ref,
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
    "/translation-rules",
    dependencies=[
        Depends(
            fx_translation_control_plane_dependency(
                action="fx_translation_view",
                resource_type="fx_translation_rule_definition",
            )
        )
    ],
)
async def list_translation_rule_definitions(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    rows = await FxTranslationReportingRepository(session).list_translation_rule_definitions(
        tenant_id=user.tenant_id
    )
    return [
        {
            "id": str(row.id),
            "rule_code": row.rule_code,
            "rule_name": row.rule_name,
            "target_reporting_currency_code": row.target_reporting_currency_code,
            "rate_policy_ref": row.rate_policy_ref,
            "version_token": row.version_token,
            "status": row.status,
        }
        for row in rows
    ]


@router.get(
    "/translation-rules/{id}/versions",
    dependencies=[
        Depends(
            fx_translation_control_plane_dependency(
                action="fx_translation_view",
                resource_type="fx_translation_rule_definition",
            )
        )
    ],
)
async def list_translation_rule_definition_versions(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    rows = await FxTranslationReportingRepository(session).list_translation_rule_versions(
        tenant_id=user.tenant_id, definition_id=id
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
    "/rate-policies",
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(
            fx_translation_control_plane_dependency(
                action="fx_rate_policy_manage",
                resource_type="fx_rate_selection_policy",
            )
        )
    ],
)
async def create_rate_selection_policy(
    body: FxRatePolicyCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    repository = FxTranslationReportingRepository(session)
    version_token = build_definition_version_token(
        DefinitionVersionTokenInput(rows=[body.model_dump(mode="json")])
    )
    try:
        row = await repository.create_rate_selection_policy(
            tenant_id=user.tenant_id,
            organisation_id=body.organisation_id,
            policy_code=body.policy_code,
            policy_name=body.policy_name,
            rate_type=body.rate_type,
            date_selector_logic_json=body.date_selector_logic_json,
            fallback_behavior_json=body.fallback_behavior_json,
            locked_rate_requirement_flag=body.locked_rate_requirement_flag,
            source_rate_provider_ref=body.source_rate_provider_ref,
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
    return {"id": str(row.id), "policy_code": row.policy_code, "version_token": row.version_token}


@router.get(
    "/rate-policies",
    dependencies=[
        Depends(
            fx_translation_control_plane_dependency(
                action="fx_translation_view",
                resource_type="fx_rate_selection_policy",
            )
        )
    ],
)
async def list_rate_selection_policies(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    rows = await FxTranslationReportingRepository(session).list_rate_selection_policies(
        tenant_id=user.tenant_id
    )
    return [
        {
            "id": str(row.id),
            "policy_code": row.policy_code,
            "policy_name": row.policy_name,
            "rate_type": row.rate_type,
            "locked_rate_requirement_flag": bool(row.locked_rate_requirement_flag),
            "version_token": row.version_token,
            "status": row.status,
        }
        for row in rows
    ]


@router.get(
    "/rate-policies/{id}/versions",
    dependencies=[
        Depends(
            fx_translation_control_plane_dependency(
                action="fx_translation_view",
                resource_type="fx_rate_selection_policy",
            )
        )
    ],
)
async def list_rate_selection_policy_versions(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    rows = await FxTranslationReportingRepository(session).list_rate_selection_policy_versions(
        tenant_id=user.tenant_id, policy_id=id
    )
    return [
        {
            "id": str(row.id),
            "policy_code": row.policy_code,
            "version_token": row.version_token,
            "status": row.status,
            "effective_from": row.effective_from.isoformat(),
        }
        for row in rows
    ]


@router.post(
    "/runs",
    response_model=FxTranslationRunCreateResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(
            fx_translation_control_plane_dependency(
                action="fx_translation_run",
                resource_type="fx_translation_run",
            )
        )
    ],
)
async def create_fx_translation_run(
    body: FxTranslationRunCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> FxTranslationRunCreateResponse:
    service = _build_service(session)
    try:
        result = await service.create_run(
            tenant_id=user.tenant_id,
            organisation_id=body.organisation_id,
            reporting_period=body.reporting_period,
            reporting_currency_code=body.reporting_currency_code,
            source_consolidation_run_refs=[
                row.model_dump(mode="json") for row in body.source_consolidation_run_refs
            ],
            created_by=user.id,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail="internal_error") from exc
    await session.flush()
    return FxTranslationRunCreateResponse(
        run_id=uuid.UUID(result["run_id"]),
        run_token=result["run_token"],
        status=result["status"],
        idempotent=bool(result["idempotent"]),
    )


@router.post(
    "/runs/{id}/execute",
    response_model=FxTranslationRunExecuteResponse,
    dependencies=[
        Depends(
            fx_translation_control_plane_dependency(
                action="fx_translation_run",
                resource_type="fx_translation_run",
            )
        )
    ],
)
async def execute_fx_translation_run(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> FxTranslationRunExecuteResponse:
    service = _build_service(session)
    try:
        result = await service.execute_run(tenant_id=user.tenant_id, run_id=id, created_by=user.id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="internal_error") from exc
    await session.flush()
    return FxTranslationRunExecuteResponse(
        run_id=uuid.UUID(result["run_id"]),
        run_token=result["run_token"],
        status=result["status"],
        metric_count=int(result["metric_count"]),
        variance_count=int(result["variance_count"]),
        evidence_count=int(result["evidence_count"]),
        idempotent=bool(result["idempotent"]),
    )


@router.get(
    "/runs/{id}",
    dependencies=[
        Depends(
            fx_translation_control_plane_dependency(
                action="fx_translation_view",
                resource_type="fx_translation_run",
            )
        )
    ],
)
async def get_fx_translation_run(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    row = await _build_service(session).get_run(tenant_id=user.tenant_id, run_id=id)
    if row is None:
        raise HTTPException(status_code=404, detail="FX translation run not found")
    return row


@router.get(
    "/runs/{id}/summary",
    dependencies=[
        Depends(
            fx_translation_control_plane_dependency(
                action="fx_translation_view",
                resource_type="fx_translation_run",
            )
        )
    ],
)
async def get_fx_translation_run_summary(
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
            fx_translation_control_plane_dependency(
                action="fx_translation_view",
                resource_type="fx_translated_metric_result",
            )
        )
    ],
)
async def list_fx_translated_metrics(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    return await _build_service(session).list_metrics(tenant_id=user.tenant_id, run_id=id)


@router.get(
    "/runs/{id}/variances",
    dependencies=[
        Depends(
            fx_translation_control_plane_dependency(
                action="fx_translation_view",
                resource_type="fx_translated_variance_result",
            )
        )
    ],
)
async def list_fx_translated_variances(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    return await _build_service(session).list_variances(tenant_id=user.tenant_id, run_id=id)


@router.get(
    "/runs/{id}/risks",
    dependencies=[
        Depends(
            fx_translation_control_plane_dependency(
                action="fx_translation_view",
                resource_type="risk_result",
            )
        )
    ],
)
async def list_fx_translated_risks(_: uuid.UUID) -> list[dict]:
    return []


@router.get(
    "/runs/{id}/anomalies",
    dependencies=[
        Depends(
            fx_translation_control_plane_dependency(
                action="fx_translation_view",
                resource_type="anomaly_result",
            )
        )
    ],
)
async def list_fx_translated_anomalies(_: uuid.UUID) -> list[dict]:
    return []


@router.get(
    "/runs/{id}/board-pack",
    dependencies=[
        Depends(
            fx_translation_control_plane_dependency(
                action="fx_translation_view",
                resource_type="board_pack_result",
            )
        )
    ],
)
async def get_fx_translated_board_pack(_: uuid.UUID) -> dict:
    return {"status": "not_generated", "sections": []}


@router.get(
    "/runs/{id}/evidence",
    dependencies=[
        Depends(
            fx_translation_control_plane_dependency(
                action="fx_translation_evidence_view",
                resource_type="fx_translation_evidence_link",
            )
        )
    ],
)
async def list_fx_translation_evidence(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    return await _build_service(session).list_evidence(tenant_id=user.tenant_id, run_id=id)

