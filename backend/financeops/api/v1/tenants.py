from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import (
    get_async_session,
    get_current_user,
    require_finance_leader,
)
from financeops.db.models.users import IamUser, UserRole
from financeops.services.credit_service import get_balance
from financeops.services.tenant_service import (
    get_tenant,
    list_workspaces,
    update_tenant_settings,
)
from financeops.services.user_service import (
    create_user,
    deactivate_user,
    get_user_by_id,
    list_tenant_users,
    update_user_role,
)

log = logging.getLogger(__name__)
router = APIRouter()


class UpdateTenantRequest(BaseModel):
    display_name: str | None = None
    timezone: str | None = None


class InviteUserRequest(BaseModel):
    email: EmailStr
    full_name: str
    role: UserRole
    password: str


class UpdateRoleRequest(BaseModel):
    role: UserRole


@router.get("/me")
async def get_my_tenant(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    """GET /api/v1/tenants/me — current tenant details."""
    tenant = await get_tenant(session, user.tenant_id)
    workspaces = await list_workspaces(session, user.tenant_id)
    return {
        "tenant_id": str(tenant.id),
        "display_name": tenant.display_name,
        "tenant_type": tenant.tenant_type.value,
        "country": tenant.country,
        "timezone": tenant.timezone,
        "status": tenant.status.value,
        "created_at": tenant.created_at.isoformat(),
        "workspaces": [
            {
                "workspace_id": str(w.id),
                "name": w.name,
                "status": w.status.value,
            }
            for w in workspaces
        ],
    }


@router.patch("/me")
async def update_my_tenant(
    body: UpdateTenantRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> dict:
    """PATCH /api/v1/tenants/me — update tenant settings."""
    tenant = await get_tenant(session, user.tenant_id)
    await update_tenant_settings(
        session,
        tenant=tenant,
        actor_user_id=user.id,
        display_name=body.display_name,
        timezone_str=body.timezone,
    )
    await session.flush()
    return {"tenant_id": str(tenant.id), "updated": True}


@router.get("/me/users")
async def list_my_users(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> dict:
    """GET /api/v1/tenants/me/users — list users in tenant."""
    users = await list_tenant_users(session, user.tenant_id)
    return {
        "users": [
            {
                "user_id": str(u.id),
                "email": u.email,
                "full_name": u.full_name,
                "role": u.role.value,
                "is_active": u.is_active,
                "mfa_enabled": u.mfa_enabled,
                "created_at": u.created_at.isoformat(),
            }
            for u in users
        ],
        "total": len(users),
    }


@router.post("/me/users", status_code=status.HTTP_201_CREATED)
async def invite_user(
    body: InviteUserRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> dict:
    """POST /api/v1/tenants/me/users — invite a new user to tenant."""
    new_user = await create_user(
        session,
        tenant_id=user.tenant_id,
        email=body.email,
        password=body.password,
        full_name=body.full_name,
        role=body.role,
    )
    await session.flush()
    return {
        "user_id": str(new_user.id),
        "email": new_user.email,
        "role": new_user.role.value,
    }


@router.patch("/me/users/{user_id}")
async def update_user(
    user_id: uuid.UUID,
    body: UpdateRoleRequest,
    session: AsyncSession = Depends(get_async_session),
    current_user: IamUser = Depends(require_finance_leader),
) -> dict:
    """PATCH /api/v1/tenants/me/users/{user_id} — update user role."""
    updated = await update_user_role(session, user_id, body.role)
    await session.flush()
    return {
        "user_id": str(updated.id),
        "role": updated.role.value,
        "updated": True,
    }


@router.delete("/me/users/{user_id}")
async def delete_user(
    user_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    current_user: IamUser = Depends(require_finance_leader),
) -> dict:
    """DELETE /api/v1/tenants/me/users/{user_id} — deactivate user (soft delete)."""
    deactivated = await deactivate_user(session, user_id)
    await session.flush()
    return {"user_id": str(deactivated.id), "deactivated": True}


@router.get("/me/credits")
async def get_credits(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    """GET /api/v1/tenants/me/credits — current credit balance + history."""
    from sqlalchemy import select, desc
    from financeops.db.models.credits import CreditTransaction

    balance = await get_balance(session, user.tenant_id)
    tx_result = await session.execute(
        select(CreditTransaction)
        .where(CreditTransaction.tenant_id == user.tenant_id)
        .order_by(desc(CreditTransaction.created_at))
        .limit(20)
    )
    transactions = tx_result.scalars().all()
    return {
        "balance": str(balance.balance),
        "reserved": str(balance.reserved),
        "available": str(balance.available),
        "transactions": [
            {
                "id": str(tx.id),
                "task_type": tx.task_type,
                "amount": str(tx.amount),
                "direction": tx.direction.value,
                "status": tx.status.value,
                "created_at": tx.created_at.isoformat(),
            }
            for tx in transactions
        ],
    }
