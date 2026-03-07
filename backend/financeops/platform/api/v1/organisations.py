from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, require_finance_leader
from financeops.db.models.users import IamUser
from financeops.platform.schemas.hierarchy import (
    EntityCreate,
    GroupCreate,
    OrganisationCreate,
    UserEntityAssignmentCreate,
    UserOrganisationAssignmentCreate,
)
from financeops.platform.services.tenancy.hierarchy_service import (
    assign_user_to_entity,
    assign_user_to_organisation,
    create_entity,
    create_group,
    create_organisation,
)

router = APIRouter()


@router.post("/organisations")
async def create_organisation_endpoint(
    body: OrganisationCreate,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> dict:
    org = await create_organisation(
        session,
        tenant_id=user.tenant_id,
        code=body.organisation_code,
        name=body.organisation_name,
        parent_organisation_id=body.parent_organisation_id,
        actor_user_id=user.id,
        correlation_id=str(getattr(request.state, "correlation_id", "") or ""),
    )
    await session.commit()
    return {"id": str(org.id), "organisation_code": org.organisation_code}


@router.post("/groups")
async def create_group_endpoint(
    body: GroupCreate,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> dict:
    group = await create_group(
        session,
        tenant_id=user.tenant_id,
        code=body.group_code,
        name=body.group_name,
        organisation_id=body.organisation_id,
        actor_user_id=user.id,
        correlation_id=str(getattr(request.state, "correlation_id", "") or ""),
    )
    await session.commit()
    return {"id": str(group.id), "group_code": group.group_code}


@router.post("/entities")
async def create_entity_endpoint(
    body: EntityCreate,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> dict:
    entity = await create_entity(
        session,
        tenant_id=user.tenant_id,
        entity_code=body.entity_code,
        entity_name=body.entity_name,
        organisation_id=body.organisation_id,
        group_id=body.group_id,
        base_currency=body.base_currency,
        country_code=body.country_code,
        actor_user_id=user.id,
        correlation_id=str(getattr(request.state, "correlation_id", "") or ""),
    )
    await session.commit()
    return {"id": str(entity.id), "entity_code": entity.entity_code}


@router.post("/assignments/organisation")
async def assign_org_endpoint(
    body: UserOrganisationAssignmentCreate,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> dict:
    assignment = await assign_user_to_organisation(
        session,
        tenant_id=user.tenant_id,
        user_id=body.user_id,
        organisation_id=body.organisation_id,
        effective_from=body.effective_from,
        effective_to=body.effective_to,
        is_primary=body.is_primary,
        actor_user_id=user.id,
        correlation_id=str(getattr(request.state, "correlation_id", "") or ""),
    )
    await session.commit()
    return {"id": str(assignment.id)}


@router.post("/assignments/entity")
async def assign_entity_endpoint(
    body: UserEntityAssignmentCreate,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> dict:
    assignment = await assign_user_to_entity(
        session,
        tenant_id=user.tenant_id,
        user_id=body.user_id,
        entity_id=body.entity_id,
        effective_from=body.effective_from,
        effective_to=body.effective_to,
        actor_user_id=user.id,
        correlation_id=str(getattr(request.state, "correlation_id", "") or ""),
    )
    await session.commit()
    return {"id": str(assignment.id)}
