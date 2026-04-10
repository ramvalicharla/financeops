from __future__ import annotations

import base64
import json
import uuid
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_tenant
from financeops.core.exceptions import ValidationError
from financeops.db.models.tenants import IamTenant
from financeops.db.transaction import commit_session
from financeops.modules.coa.models import ErpAccountMapping
from financeops.modules.org_setup.api.schemas import (
    ModuleSelectionReviewRequest,
    ModuleSelectionReviewResponse,
    OrgEntityResponse,
    OrgOwnershipResponse,
    OrgSetupProgressResponse,
    OrgSetupSummaryResponse,
    OrgGroupResponse,
    OrgEntityErpConfigResponse,
    OwnershipTreeResponse,
    ReviewRow,
    Step1ConfirmRequest,
    Step1ConfirmResponse,
    Step1DraftResponse,
    Step1Request,
    Step1Response,
    Step2ConfirmRequest,
    Step2ConfirmResponse,
    Step2DraftResponse,
    Step2Request,
    Step2Response,
    Step3Request,
    Step3Response,
    Step4Request,
    Step4Response,
    Step5Request,
    Step5Response,
    Step5EntitySummary,
    Step6Request,
    Step6Response,
    UpdateOrgEntityRequest,
)
from financeops.modules.org_setup.application.org_setup_service import OrgSetupService
from financeops.modules.service_registry.models import ModuleRegistry

router = APIRouter(prefix="/org-setup", tags=["org-setup"])


def _encode_setup_draft(*, tenant_id: uuid.UUID, step: str, payload: dict[str, Any]) -> str:
    serialized = json.dumps(
        {
            "tenant_id": str(tenant_id),
            "step": step,
            "payload": payload,
        },
        separators=(",", ":"),
        sort_keys=True,
        default=str,
    )
    return base64.urlsafe_b64encode(serialized.encode("utf-8")).decode("utf-8")


def _decode_setup_draft(*, draft_id: str, tenant_id: uuid.UUID, step: str) -> dict[str, Any]:
    padded = draft_id + "=" * (-len(draft_id) % 4)
    payload = json.loads(base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8"))
    if payload.get("tenant_id") != str(tenant_id):
        raise ValidationError("draft_id does not belong to the current tenant")
    if payload.get("step") != step:
        raise ValidationError("draft_id does not match the expected setup step")
    draft_payload = payload.get("payload")
    if not isinstance(draft_payload, dict):
        raise ValidationError("draft_id payload is invalid")
    return draft_payload


def _step1_review_rows(payload: Step1Request) -> list[ReviewRow]:
    return [
        ReviewRow(label="Organization", value=payload.group_name),
        ReviewRow(label="Country", value=payload.country_of_incorp),
        ReviewRow(label="Country code", value=payload.country_code),
        ReviewRow(label="Base currency", value=payload.functional_currency),
        ReviewRow(label="Reporting currency", value=payload.reporting_currency),
        ReviewRow(label="Website", value=payload.website or "Not provided"),
    ]


def _step2_review_rows(payload: Step2Request) -> list[ReviewRow]:
    entity = payload.entities[0]
    return [
        ReviewRow(label="Organization group", value=str(payload.group_id)),
        ReviewRow(label="Legal name", value=entity.legal_name),
        ReviewRow(label="Display name", value=entity.display_name or "Not provided"),
        ReviewRow(label="Entity type", value=entity.entity_type),
        ReviewRow(label="Country code", value=entity.country_code),
        ReviewRow(label="Functional currency", value=entity.functional_currency),
        ReviewRow(label="Reporting currency", value=entity.reporting_currency),
        ReviewRow(label="Framework", value=entity.applicable_gaap),
    ]


def _module_review_rows(module_names: list[str]) -> list[ReviewRow]:
    if not module_names:
        return [ReviewRow(label="Selected modules", value="No modules enabled in backend state yet")]
    return [
        ReviewRow(label=f"Module {index + 1}", value=module_name)
        for index, module_name in enumerate(module_names)
    ]


@router.get("/progress", response_model=OrgSetupProgressResponse)
async def get_progress(
    session: AsyncSession = Depends(get_async_session),
    tenant: IamTenant = Depends(get_current_tenant),
) -> OrgSetupProgressResponse:
    service = OrgSetupService(session)
    progress = await service.get_or_create_progress(tenant.id)
    coa_status = await service.get_coa_status(tenant.id)
    onboarding_score = await service.get_onboarding_score(tenant.id)
    return OrgSetupProgressResponse(
        id=progress.id,
        tenant_id=progress.tenant_id,
        current_step=min(max(progress.current_step, 1), 4),
        step1_data=progress.step1_data,
        step2_data=progress.step2_data,
        step3_data=progress.step3_data,
        step4_data=progress.step4_data,
        step5_data=progress.step5_data,
        step6_data=progress.step6_data,
        coa_status=coa_status,
        onboarding_score=onboarding_score,
        completed_at=progress.completed_at,
        created_at=progress.created_at,
        updated_at=progress.updated_at,
    )


@router.post("/step1", response_model=Step1Response)
async def submit_step1(
    payload: Step1Request,
    session: AsyncSession = Depends(get_async_session),
    tenant: IamTenant = Depends(get_current_tenant),
) -> Step1Response:
    service = OrgSetupService(session)
    group = await service.submit_step1(tenant.id, payload.model_dump())
    await commit_session(session)
    await session.refresh(group)
    return Step1Response(group=OrgGroupResponse.model_validate(group, from_attributes=True))


@router.post("/step1/draft", response_model=Step1DraftResponse)
async def draft_step1(
    payload: Step1Request,
    tenant: IamTenant = Depends(get_current_tenant),
) -> Step1DraftResponse:
    review_rows = _step1_review_rows(payload)
    draft_payload = payload.model_dump(mode="json")
    return Step1DraftResponse(
        draft_id=_encode_setup_draft(
            tenant_id=tenant.id,
            step="create_organization",
            payload=draft_payload,
        ),
        review_rows=review_rows,
        payload=draft_payload,
    )


@router.post("/step1/confirm", response_model=Step1ConfirmResponse)
async def confirm_step1(
    body: Step1ConfirmRequest,
    session: AsyncSession = Depends(get_async_session),
    tenant: IamTenant = Depends(get_current_tenant),
) -> Step1ConfirmResponse:
    draft_payload = _decode_setup_draft(
        draft_id=body.draft_id,
        tenant_id=tenant.id,
        step="create_organization",
    )
    payload = Step1Request.model_validate(draft_payload)
    service = OrgSetupService(session)
    group = await service.submit_step1(tenant.id, payload.model_dump())
    await commit_session(session)
    await session.refresh(group)
    return Step1ConfirmResponse(
        draft_id=body.draft_id,
        review_rows=_step1_review_rows(payload),
        group=OrgGroupResponse.model_validate(group, from_attributes=True),
    )


@router.post("/step2", response_model=Step2Response)
async def submit_step2(
    payload: Step2Request,
    session: AsyncSession = Depends(get_async_session),
    tenant: IamTenant = Depends(get_current_tenant),
) -> Step2Response:
    service = OrgSetupService(session)
    rows = await service.submit_step2(
        tenant.id,
        payload.group_id,
        [item.model_dump() for item in payload.entities],
    )
    await commit_session(session)
    for item in rows:
        await session.refresh(item)
    return Step2Response(
        entities=[OrgEntityResponse.model_validate(item, from_attributes=True) for item in rows]
    )


@router.post("/step2/draft", response_model=Step2DraftResponse)
async def draft_step2(
    payload: Step2Request,
    tenant: IamTenant = Depends(get_current_tenant),
) -> Step2DraftResponse:
    review_rows = _step2_review_rows(payload)
    draft_payload = payload.model_dump(mode="json")
    return Step2DraftResponse(
        draft_id=_encode_setup_draft(
            tenant_id=tenant.id,
            step="create_entity",
            payload=draft_payload,
        ),
        review_rows=review_rows,
        payload=draft_payload,
    )


@router.post("/step2/confirm", response_model=Step2ConfirmResponse)
async def confirm_step2(
    body: Step2ConfirmRequest,
    session: AsyncSession = Depends(get_async_session),
    tenant: IamTenant = Depends(get_current_tenant),
) -> Step2ConfirmResponse:
    draft_payload = _decode_setup_draft(
        draft_id=body.draft_id,
        tenant_id=tenant.id,
        step="create_entity",
    )
    payload = Step2Request.model_validate(draft_payload)
    service = OrgSetupService(session)
    rows = await service.submit_step2(
        tenant.id,
        payload.group_id,
        [item.model_dump() for item in payload.entities],
    )
    await commit_session(session)
    for item in rows:
        await session.refresh(item)
    return Step2ConfirmResponse(
        draft_id=body.draft_id,
        review_rows=_step2_review_rows(payload),
        entities=[OrgEntityResponse.model_validate(item, from_attributes=True) for item in rows],
    )


@router.post("/step3/modules/review", response_model=ModuleSelectionReviewResponse)
async def review_step3_modules(
    body: ModuleSelectionReviewRequest,
    session: AsyncSession = Depends(get_async_session),
    tenant: IamTenant = Depends(get_current_tenant),
) -> ModuleSelectionReviewResponse:
    requested_module_names = [item.strip() for item in body.module_names if item.strip()]
    unique_module_names = list(dict.fromkeys(requested_module_names))
    if unique_module_names:
        rows = (
            await session.execute(
                select(ModuleRegistry.module_name).where(ModuleRegistry.module_name.in_(unique_module_names))
            )
        ).scalars().all()
        missing = sorted(set(unique_module_names) - set(rows))
        if missing:
            raise ValidationError(f"Unknown modules in review request: {', '.join(missing)}")

    payload = {"module_names": unique_module_names, "tenant_id": str(tenant.id)}
    return ModuleSelectionReviewResponse(
        draft_id=_encode_setup_draft(
            tenant_id=tenant.id,
            step="review_module_selection",
            payload=payload,
        ),
        review_rows=_module_review_rows(unique_module_names),
        payload=payload,
    )


@router.post("/step3", response_model=Step3Response)
async def submit_step3(
    payload: Step3Request,
    session: AsyncSession = Depends(get_async_session),
    tenant: IamTenant = Depends(get_current_tenant),
) -> Step3Response:
    service = OrgSetupService(session)
    rows = await service.submit_step3(
        tenant.id,
        [item.model_dump() for item in payload.relationships],
    )
    await commit_session(session)
    for item in rows:
        await session.refresh(item)
    return Step3Response(
        ownership=[OrgOwnershipResponse.model_validate(item, from_attributes=True) for item in rows]
    )


@router.post("/step4", response_model=Step4Response)
async def submit_step4(
    payload: Step4Request,
    session: AsyncSession = Depends(get_async_session),
    tenant: IamTenant = Depends(get_current_tenant),
) -> Step4Response:
    service = OrgSetupService(session)
    rows = await service.submit_step4(
        tenant.id,
        [item.model_dump() for item in payload.configs],
    )
    await commit_session(session)
    for item in rows:
        await session.refresh(item)
    return Step4Response(
        configs=[OrgEntityErpConfigResponse.model_validate(item, from_attributes=True) for item in rows]
    )


@router.post("/step5", response_model=Step5Response)
async def submit_step5(
    payload: Step5Request,
    session: AsyncSession = Depends(get_async_session),
    tenant: IamTenant = Depends(get_current_tenant),
) -> Step5Response:
    service = OrgSetupService(session)
    summaries = await service.submit_step5(
        tenant.id,
        [item.model_dump() for item in payload.entity_templates],
    )
    await commit_session(session)
    return Step5Response(
        initialised_count=len(summaries),
        entity_summaries=[
            Step5EntitySummary(
                entity_id=uuid.UUID(str(item["entity_id"])),
                template_code=str(item["template_code"]),
                account_count=int(item["account_count"]),
            )
            for item in summaries
        ],
        coa_status=await service.get_coa_status(tenant.id),
        onboarding_score=await service.get_onboarding_score(tenant.id),
    )


@router.post("/step6", response_model=Step6Response)
async def submit_step6(
    payload: Step6Request,
    session: AsyncSession = Depends(get_async_session),
    tenant: IamTenant = Depends(get_current_tenant),
) -> Step6Response:
    mapping_ids = list(payload.confirmed_mapping_ids)
    if payload.auto_confirm_above is not None:
        try:
            threshold = Decimal(payload.auto_confirm_above)
        except Exception as exc:  # noqa: BLE001
            raise ValidationError("auto_confirm_above must be a Decimal string") from exc
        rows = (
            await session.execute(
                select(ErpAccountMapping.id).where(
                    ErpAccountMapping.tenant_id == tenant.id,
                    ErpAccountMapping.id.in_(mapping_ids),
                    ErpAccountMapping.mapping_confidence.is_not(None),
                    ErpAccountMapping.mapping_confidence >= threshold,
                )
            )
        ).scalars().all()
        mapping_ids = list(rows)

    service = OrgSetupService(session)
    confirmed_count = await service.submit_step6(
        tenant.id,
        mapping_ids,
    )
    await commit_session(session)

    unmapped_count = int(
        (
            await session.execute(
                select(func.count())
                .select_from(ErpAccountMapping)
                .where(ErpAccountMapping.tenant_id == tenant.id)
                .where(
                    or_(
                        ErpAccountMapping.tenant_coa_account_id.is_(None),
                        ErpAccountMapping.is_confirmed.is_(False),
                    )
                )
            )
        ).scalar_one()
    )

    return Step6Response(
        confirmed_count=confirmed_count,
        unmapped_count=unmapped_count,
        setup_complete=True,
        coa_status=await service.get_coa_status(tenant.id),
        onboarding_score=await service.get_onboarding_score(tenant.id),
    )


@router.get("/summary", response_model=OrgSetupSummaryResponse)
async def get_setup_summary(
    session: AsyncSession = Depends(get_async_session),
    tenant: IamTenant = Depends(get_current_tenant),
) -> OrgSetupSummaryResponse:
    service = OrgSetupService(session)
    payload = await service.get_setup_summary(tenant.id)
    group = payload.get("group")
    return OrgSetupSummaryResponse(
        group=OrgGroupResponse.model_validate(group, from_attributes=True) if group is not None else None,
        entities=[
            OrgEntityResponse.model_validate(item, from_attributes=True) for item in payload["entities"]
        ],
        ownership=[
            OrgOwnershipResponse.model_validate(item, from_attributes=True) for item in payload["ownership"]
        ],
        erp_configs=[
            OrgEntityErpConfigResponse.model_validate(item, from_attributes=True)
            for item in payload["erp_configs"]
        ],
        current_step=int(payload["current_step"]),
        completed_at=payload["completed_at"],
        coa_account_count=int(payload["coa_account_count"]),
        coa_status=str(payload["coa_status"]),
        onboarding_score=int(payload["onboarding_score"]),
        mapping_summary=payload["mapping_summary"],
    )


@router.get("/entities", response_model=list[OrgEntityResponse])
async def list_entities(
    session: AsyncSession = Depends(get_async_session),
    tenant: IamTenant = Depends(get_current_tenant),
) -> list[OrgEntityResponse]:
    service = OrgSetupService(session)
    rows = await service.get_entities(tenant.id)
    return [OrgEntityResponse.model_validate(item, from_attributes=True) for item in rows]


@router.get("/entities/{entity_id}", response_model=OrgEntityResponse)
async def get_entity(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    tenant: IamTenant = Depends(get_current_tenant),
) -> OrgEntityResponse:
    service = OrgSetupService(session)
    row = await service.get_entity(tenant.id, entity_id)
    return OrgEntityResponse.model_validate(row, from_attributes=True)


@router.get("/ownership-tree", response_model=OwnershipTreeResponse)
async def get_ownership_tree(
    session: AsyncSession = Depends(get_async_session),
    tenant: IamTenant = Depends(get_current_tenant),
) -> OwnershipTreeResponse:
    service = OrgSetupService(session)
    payload = await service.get_ownership_tree(tenant.id)
    return OwnershipTreeResponse(**payload)


@router.patch("/entities/{entity_id}", response_model=OrgEntityResponse)
async def update_entity(
    entity_id: uuid.UUID,
    body: UpdateOrgEntityRequest,
    session: AsyncSession = Depends(get_async_session),
    tenant: IamTenant = Depends(get_current_tenant),
) -> OrgEntityResponse:
    service = OrgSetupService(session)
    row = await service.update_entity(
        tenant.id,
        entity_id,
        body.model_dump(exclude_unset=True),
    )
    return OrgEntityResponse.model_validate(row, from_attributes=True)
