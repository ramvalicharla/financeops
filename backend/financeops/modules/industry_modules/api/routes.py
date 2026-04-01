from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user
from financeops.core.exceptions import AuthorizationError
from financeops.db.models.users import IamUser, UserRole
from financeops.modules.industry_modules.application.service import (
    create_accrual_schedule,
    create_fixed_asset,
    create_lease,
    create_prepaid_schedule,
    create_revenue_contract,
    get_asset_schedule,
    get_lease_schedule,
    get_revenue_schedule,
    list_modules,
    set_module_status,
)
from financeops.modules.industry_modules.schemas import (
    AccrualCreateRequest,
    FixedAssetCreateRequest,
    LeaseCreateRequest,
    ModuleToggleRequest,
    PrepaidCreateRequest,
    RevenueContractCreateRequest,
)
from financeops.shared_kernel.response import ok

router = APIRouter(prefix="/modules", tags=["Industry Modules"])

_ADMIN_ROLES = {
    UserRole.platform_owner,
    UserRole.platform_admin,
    UserRole.super_admin,
}
_FINANCE_ROLES = {
    UserRole.platform_owner,
    UserRole.platform_admin,
    UserRole.super_admin,
    UserRole.finance_leader,
    UserRole.finance_team,
}


def _assert_admin(user: IamUser) -> None:
    if user.role not in _ADMIN_ROLES:
        raise AuthorizationError("Platform admin role required.")


def _assert_finance(user: IamUser) -> None:
    if user.role not in _FINANCE_ROLES:
        raise AuthorizationError("Finance role required.")


@router.get("")
async def list_modules_endpoint(
    request: Request,
    db: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    _assert_finance(user)
    payload = await list_modules(
        db,
        tenant_id=user.tenant_id,
    )
    return ok(
        [row.model_dump(mode="json") for row in payload],
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.post("/{module_name}/enable")
async def enable_module_endpoint(
    request: Request,
    module_name: str,
    body: ModuleToggleRequest,
    db: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    _assert_admin(user)
    payload = await set_module_status(
        db,
        tenant_id=user.tenant_id,
        actor_user_id=user.id,
        module_name=module_name,
        status="ENABLED",
        configuration_json=body.configuration_json,
    )
    await db.commit()
    return ok(payload.model_dump(mode="json"), request_id=getattr(request.state, "request_id", None)).model_dump(mode="json")


@router.post("/{module_name}/disable")
async def disable_module_endpoint(
    request: Request,
    module_name: str,
    body: ModuleToggleRequest,
    db: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    _assert_admin(user)
    payload = await set_module_status(
        db,
        tenant_id=user.tenant_id,
        actor_user_id=user.id,
        module_name=module_name,
        status="DISABLED",
        configuration_json=body.configuration_json,
    )
    await db.commit()
    return ok(payload.model_dump(mode="json"), request_id=getattr(request.state, "request_id", None)).model_dump(mode="json")


@router.post("/lease/create")
async def create_lease_endpoint(
    request: Request,
    body: LeaseCreateRequest,
    db: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    _assert_finance(user)
    payload = await create_lease(
        db,
        tenant_id=user.tenant_id,
        actor_user_id=user.id,
        payload=body,
    )
    await db.commit()
    return ok(payload.model_dump(mode="json"), request_id=getattr(request.state, "request_id", None)).model_dump(mode="json")


@router.get("/lease/schedule")
async def get_lease_schedule_endpoint(
    request: Request,
    lease_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    _assert_finance(user)
    rows = await get_lease_schedule(
        db,
        tenant_id=user.tenant_id,
        lease_id=lease_id,
    )
    return ok(
        [row.model_dump(mode="json") for row in rows],
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.post("/revenue/create-contract")
async def create_revenue_contract_endpoint(
    request: Request,
    body: RevenueContractCreateRequest,
    db: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    _assert_finance(user)
    payload = await create_revenue_contract(
        db,
        tenant_id=user.tenant_id,
        actor_user_id=user.id,
        payload=body,
    )
    await db.commit()
    return ok(payload.model_dump(mode="json"), request_id=getattr(request.state, "request_id", None)).model_dump(mode="json")


@router.get("/revenue/schedule")
async def get_revenue_schedule_endpoint(
    request: Request,
    contract_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    _assert_finance(user)
    rows = await get_revenue_schedule(
        db,
        tenant_id=user.tenant_id,
        contract_id=contract_id,
    )
    return ok(
        [row.model_dump(mode="json") for row in rows],
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.post("/assets/create")
async def create_asset_endpoint(
    request: Request,
    body: FixedAssetCreateRequest,
    db: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    _assert_finance(user)
    payload = await create_fixed_asset(
        db,
        tenant_id=user.tenant_id,
        actor_user_id=user.id,
        payload=body,
    )
    await db.commit()
    return ok(payload.model_dump(mode="json"), request_id=getattr(request.state, "request_id", None)).model_dump(mode="json")


@router.get("/assets/schedule")
async def get_asset_schedule_endpoint(
    request: Request,
    asset_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    _assert_finance(user)
    rows = await get_asset_schedule(
        db,
        tenant_id=user.tenant_id,
        asset_id=asset_id,
    )
    return ok(
        [row.model_dump(mode="json") for row in rows],
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.post("/prepaid/create")
async def create_prepaid_endpoint(
    request: Request,
    body: PrepaidCreateRequest,
    db: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    _assert_finance(user)
    payload = await create_prepaid_schedule(
        db,
        tenant_id=user.tenant_id,
        actor_user_id=user.id,
        payload=body,
    )
    await db.commit()
    return ok(payload.model_dump(mode="json"), request_id=getattr(request.state, "request_id", None)).model_dump(mode="json")


@router.post("/accrual/create")
async def create_accrual_endpoint(
    request: Request,
    body: AccrualCreateRequest,
    db: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    _assert_finance(user)
    payload = await create_accrual_schedule(
        db,
        tenant_id=user.tenant_id,
        actor_user_id=user.id,
        payload=body,
    )
    await db.commit()
    return ok(payload.model_dump(mode="json"), request_id=getattr(request.state, "request_id", None)).model_dump(mode="json")

