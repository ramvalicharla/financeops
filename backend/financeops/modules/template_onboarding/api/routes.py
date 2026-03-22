from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user
from financeops.db.models.users import IamUser
from financeops.modules.template_onboarding.models import OnboardingState
from financeops.modules.template_onboarding.service import (
    TemplateAlreadyAppliedError,
    apply_template,
    complete_onboarding,
    get_or_create_onboarding_state,
    update_onboarding_step,
)
from financeops.modules.template_onboarding.templates import (
    TEMPLATE_REGISTRY,
    get_template,
)
from financeops.shared_kernel.pagination import Paginated

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


class OnboardingStateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    current_step: int
    industry: str | None = None
    template_applied: bool
    template_applied_at: datetime | None = None
    template_id: str | None = None
    erp_connected: bool
    completed: bool
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class UpdateOnboardingStateRequest(BaseModel):
    current_step: int | None = None
    industry: str | None = None
    erp_connected: bool | None = None


class TemplateSummaryResponse(BaseModel):
    id: str
    name: str
    industry: str
    description: str
    board_pack_sections_count: int
    report_definitions_count: int


class TemplateDetailResponse(BaseModel):
    id: str
    name: str
    industry: str
    description: str
    board_pack_sections: list[dict[str, Any]]
    report_definitions: list[dict[str, Any]]
    delivery_schedule: dict[str, Any]


class ApplyTemplateRequest(BaseModel):
    template_id: str


class ApplyTemplateResponse(BaseModel):
    board_pack_definition_id: str
    report_definition_ids: list[str]
    delivery_schedule_id: str
    step: int


async def _reload_state(db: AsyncSession, state_id: uuid.UUID) -> OnboardingState:
    row = (
        await db.execute(
            select(OnboardingState).where(OnboardingState.id == state_id)
        )
    ).scalar_one()
    return row


@router.get("/state", response_model=OnboardingStateResponse)
async def get_onboarding_state(
    db: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> OnboardingStateResponse:
    row = await get_or_create_onboarding_state(session=db, tenant_id=user.tenant_id)
    await db.commit()
    refreshed = await _reload_state(db, row.id)
    return OnboardingStateResponse.model_validate(refreshed)


@router.patch("/state", response_model=OnboardingStateResponse)
async def patch_onboarding_state(
    body: UpdateOnboardingStateRequest,
    db: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> OnboardingStateResponse:
    if body.current_step is not None:
        extra_updates = body.model_dump(exclude_unset=True, exclude={"current_step"})
        try:
            row = await update_onboarding_step(
                session=db,
                tenant_id=user.tenant_id,
                step=body.current_step,
                **extra_updates,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="internal_error") from exc
    else:
        row = await get_or_create_onboarding_state(session=db, tenant_id=user.tenant_id)
        if body.industry is not None:
            row.industry = body.industry
        if body.erp_connected is not None:
            row.erp_connected = body.erp_connected
        row.updated_at = datetime.now(UTC)
        await db.flush()

    await db.commit()
    refreshed = await _reload_state(db, row.id)
    return OnboardingStateResponse.model_validate(refreshed)


@router.get("/templates", response_model=Paginated[TemplateSummaryResponse] | list[TemplateSummaryResponse])
async def list_templates(
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> Paginated[TemplateSummaryResponse] | list[TemplateSummaryResponse]:
    rows: list[TemplateSummaryResponse] = []
    for template in TEMPLATE_REGISTRY.values():
        rows.append(
            TemplateSummaryResponse(
                id=template.id,
                name=template.name,
                industry=template.industry,
                description=template.description,
                board_pack_sections_count=len(template.board_pack_sections),
                report_definitions_count=len(template.report_definitions),
            )
        )
    total = len(rows)
    paged_rows = rows[offset : offset + limit]
    if "limit" not in request.query_params and "offset" not in request.query_params:
        return paged_rows
    return Paginated[TemplateSummaryResponse](data=paged_rows, total=total, limit=limit, offset=offset)


@router.get("/templates/{template_id}", response_model=TemplateDetailResponse)
async def get_template_detail(template_id: str) -> TemplateDetailResponse:
    template = get_template(template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")
    return TemplateDetailResponse(
        id=template.id,
        name=template.name,
        industry=template.industry,
        description=template.description,
        board_pack_sections=template.board_pack_sections,
        report_definitions=template.report_definitions,
        delivery_schedule=template.delivery_schedule,
    )


@router.post("/apply", response_model=ApplyTemplateResponse)
async def apply_onboarding_template(
    body: ApplyTemplateRequest,
    db: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> ApplyTemplateResponse:
    if get_template(body.template_id) is None:
        raise HTTPException(status_code=422, detail="Invalid template_id")

    try:
        result = await apply_template(
            session=db,
            tenant_id=user.tenant_id,
            template_id=body.template_id,
            user_id=user.id,
        )
    except TemplateAlreadyAppliedError as exc:
        raise HTTPException(status_code=409, detail="Template already applied") from exc

    await db.commit()
    return ApplyTemplateResponse(
        board_pack_definition_id=result["board_pack_definition_id"],
        report_definition_ids=result["report_definition_ids"],
        delivery_schedule_id=result["delivery_schedule_id"],
        step=int(result["step"]),
    )


@router.post("/complete", response_model=OnboardingStateResponse)
async def finish_onboarding(
    db: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> OnboardingStateResponse:
    row = await complete_onboarding(session=db, tenant_id=user.tenant_id)
    await db.commit()
    refreshed = await _reload_state(db, row.id)
    return OnboardingStateResponse.model_validate(refreshed)
