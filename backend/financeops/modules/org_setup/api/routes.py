from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user
from financeops.core.exceptions import ValidationError
from financeops.db.models.users import IamUser
from financeops.modules.coa.models import ErpAccountMapping
from financeops.modules.org_setup.api.schemas import (
    OrgEntityResponse,
    OrgOwnershipResponse,
    OrgSetupProgressResponse,
    OrgSetupSummaryResponse,
    OrgGroupResponse,
    OrgEntityErpConfigResponse,
    OwnershipTreeResponse,
    Step1Request,
    Step1Response,
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

router = APIRouter(prefix="/org-setup", tags=["org-setup"])


@router.get("/progress", response_model=OrgSetupProgressResponse)
async def get_progress(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> OrgSetupProgressResponse:
    service = OrgSetupService(session)
    progress = await service.get_or_create_progress(user.tenant_id)
    return OrgSetupProgressResponse.model_validate(progress, from_attributes=True)


@router.post("/step1", response_model=Step1Response)
async def submit_step1(
    body: Step1Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> Step1Response:
    service = OrgSetupService(session)
    group = await service.submit_step1(user.tenant_id, body.model_dump())
    return Step1Response(group=OrgGroupResponse.model_validate(group, from_attributes=True))


@router.post("/step2", response_model=Step2Response)
async def submit_step2(
    body: Step2Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> Step2Response:
    service = OrgSetupService(session)
    rows = await service.submit_step2(
        user.tenant_id,
        body.group_id,
        [item.model_dump() for item in body.entities],
    )
    return Step2Response(
        entities=[OrgEntityResponse.model_validate(item, from_attributes=True) for item in rows]
    )


@router.post("/step3", response_model=Step3Response)
async def submit_step3(
    body: Step3Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> Step3Response:
    service = OrgSetupService(session)
    rows = await service.submit_step3(
        user.tenant_id,
        [item.model_dump() for item in body.relationships],
    )
    return Step3Response(
        ownership=[OrgOwnershipResponse.model_validate(item, from_attributes=True) for item in rows]
    )


@router.post("/step4", response_model=Step4Response)
async def submit_step4(
    body: Step4Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> Step4Response:
    service = OrgSetupService(session)
    rows = await service.submit_step4(
        user.tenant_id,
        [item.model_dump() for item in body.configs],
    )
    return Step4Response(
        configs=[OrgEntityErpConfigResponse.model_validate(item, from_attributes=True) for item in rows]
    )


@router.post("/step5", response_model=Step5Response)
async def submit_step5(
    body: Step5Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> Step5Response:
    service = OrgSetupService(session)
    summaries = await service.submit_step5(
        user.tenant_id,
        [item.model_dump() for item in body.entity_templates],
    )
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
    )


@router.post("/step6", response_model=Step6Response)
async def submit_step6(
    body: Step6Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> Step6Response:
    mapping_ids = list(body.confirmed_mapping_ids)
    if body.auto_confirm_above is not None:
        try:
            threshold = Decimal(body.auto_confirm_above)
        except Exception as exc:  # noqa: BLE001
            raise ValidationError("auto_confirm_above must be a Decimal string") from exc
        rows = (
            await session.execute(
                select(ErpAccountMapping.id).where(
                    ErpAccountMapping.tenant_id == user.tenant_id,
                    ErpAccountMapping.id.in_(mapping_ids),
                    ErpAccountMapping.mapping_confidence.is_not(None),
                    ErpAccountMapping.mapping_confidence >= threshold,
                )
            )
        ).scalars().all()
        mapping_ids = list(rows)

    service = OrgSetupService(session)
    confirmed_count = await service.submit_step6(
        user.tenant_id,
        mapping_ids,
        confirmed_by=user.id,
    )

    unmapped_count = int(
        (
            await session.execute(
                select(func.count())
                .select_from(ErpAccountMapping)
                .where(ErpAccountMapping.tenant_id == user.tenant_id)
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
    )


@router.get("/summary", response_model=OrgSetupSummaryResponse)
async def get_setup_summary(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> OrgSetupSummaryResponse:
    service = OrgSetupService(session)
    payload = await service.get_setup_summary(user.tenant_id)
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
        coa_account_count=int(payload["coa_account_count"]),
        mapping_summary=payload["mapping_summary"],
    )


@router.get("/entities", response_model=list[OrgEntityResponse])
async def list_entities(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[OrgEntityResponse]:
    service = OrgSetupService(session)
    rows = await service.get_entities(user.tenant_id)
    return [OrgEntityResponse.model_validate(item, from_attributes=True) for item in rows]


@router.get("/entities/{entity_id}", response_model=OrgEntityResponse)
async def get_entity(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> OrgEntityResponse:
    service = OrgSetupService(session)
    row = await service.get_entity(user.tenant_id, entity_id)
    return OrgEntityResponse.model_validate(row, from_attributes=True)


@router.get("/ownership-tree", response_model=OwnershipTreeResponse)
async def get_ownership_tree(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> OwnershipTreeResponse:
    service = OrgSetupService(session)
    payload = await service.get_ownership_tree(user.tenant_id)
    return OwnershipTreeResponse(**payload)


@router.patch("/entities/{entity_id}", response_model=OrgEntityResponse)
async def update_entity(
    entity_id: uuid.UUID,
    body: UpdateOrgEntityRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> OrgEntityResponse:
    service = OrgSetupService(session)
    row = await service.update_entity(
        user.tenant_id,
        entity_id,
        body.model_dump(exclude_unset=True),
    )
    return OrgEntityResponse.model_validate(row, from_attributes=True)
