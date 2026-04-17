from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import (
    get_async_session,
    get_current_user,
    require_user_plane_permission,
)
from financeops.config import settings
from financeops.core.exceptions import NotFoundError, ValidationError
from financeops.db.models.tenants import IamTenant
from financeops.db.models.users import IamUser, UserRole
from financeops.modules.notifications.service import send_notification
from financeops.platform.db.models.user_membership import CpUserEntityAssignment
from financeops.platform.services.rbac.user_plane import is_tenant_assignable_role
from financeops.services.user_service import (
    list_tenant_users,
    normalize_email,
    offboard_user,
    update_user_role,
)
from financeops.shared_kernel.idempotency import optional_idempotency_key

router = APIRouter()

tenant_user_manage_guard = require_user_plane_permission(
    resource_type="tenant_user",
    action="manage",
    fallback_roles={
        UserRole.super_admin,
        UserRole.platform_owner,
        UserRole.platform_admin,
        UserRole.finance_leader,
    },
    fallback_error_message="finance_approver role required",
)


class OffboardUserRequest(BaseModel):
    reason: str = "Offboarded"


class InviteUserRequest(BaseModel):
    email: EmailStr
    full_name: str
    role: UserRole
    entity_ids: list[uuid.UUID] = []


class UpdateRoleRequest(BaseModel):
    role: UserRole


def _validate_tenant_assignable_role(role: UserRole) -> UserRole:
    if not is_tenant_assignable_role(role):
        raise HTTPException(
            status_code=422,
            detail="Platform roles cannot be assigned from tenant user management",
        )
    return role


def _serialize_user(user: IamUser) -> dict[str, str | bool | None]:
    return {
        "user_id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.value,
        "is_active": user.is_active,
        "mfa_enabled": user.mfa_enabled,
        "invite_accepted_at": (
            user.invite_accepted_at.isoformat() if user.invite_accepted_at else None
        ),
        "created_at": user.created_at.isoformat(),
    }


async def _get_tenant_user_or_404(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
) -> IamUser:
    user = (
        await session.execute(
            select(IamUser).where(
                IamUser.id == user_id,
                IamUser.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.get("/users")
async def list_users(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(tenant_user_manage_guard),
) -> dict:
    users = await list_tenant_users(session, user.tenant_id)
    return {
        "users": [_serialize_user(row) for row in users],
        "total": len(users),
    }


@router.post("/users", status_code=status.HTTP_201_CREATED)
async def invite_user(
    body: InviteUserRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(tenant_user_manage_guard),
    _: str | None = Depends(optional_idempotency_key),
) -> dict:
    _validate_tenant_assignable_role(body.role)

    tenant = await session.get(IamTenant, user.tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    if not tenant.org_setup_complete:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "ORG_SETUP_REQUIRED",
                "message": (
                    "Organisation setup must be completed before inviting team members."
                ),
                "current_step": tenant.org_setup_step,
            },
        )

    invite_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(invite_token.encode("utf-8")).hexdigest()
    new_user = IamUser(
        tenant_id=user.tenant_id,
        email=normalize_email(body.email),
        full_name=body.full_name.strip(),
        role=body.role,
        hashed_password="INVITE_PENDING",
        force_mfa_setup=True,
        is_active=False,
        invite_token_hash=token_hash,
        invite_expires_at=datetime.now(UTC) + timedelta(hours=48),
    )
    session.add(new_user)
    await session.flush()

    for entity_id in body.entity_ids:
        session.add(
            CpUserEntityAssignment(
                tenant_id=user.tenant_id,
                user_id=new_user.id,
                entity_id=entity_id,
                is_active=True,
            )
        )

    frontend_base = str(getattr(settings, "FRONTEND_URL", "http://localhost:3000")).rstrip("/")
    invite_url = f"{frontend_base}/accept-invite?token={invite_token}"
    await send_notification(
        session,
        tenant_id=user.tenant_id,
        recipient_user_id=new_user.id,
        notification_type="user_invited",
        title="You've been invited to FinanceOps",
        body=(
            f"{user.full_name} invited you to join {tenant.display_name}. "
            f"Accept invitation: {invite_url}"
        ),
        action_url=invite_url,
        metadata={
            "invitee_name": body.full_name,
            "inviter_name": user.full_name,
            "company_name": tenant.display_name,
            "invite_url": invite_url,
            "unsubscribe_url": f"{frontend_base}/settings/privacy",
        },
    )
    await session.flush()
    return {
        "user_id": str(new_user.id),
        "email": new_user.email,
        "role": new_user.role.value,
        "message": f"Invitation queued for {new_user.email}",
    }


@router.get("/users/{user_id}")
async def get_user(
    user_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(tenant_user_manage_guard),
) -> dict:
    row = await _get_tenant_user_or_404(session, tenant_id=user.tenant_id, user_id=user_id)
    return _serialize_user(row)


@router.patch("/users/{user_id}/role")
async def update_user_role_endpoint(
    user_id: uuid.UUID,
    body: UpdateRoleRequest,
    session: AsyncSession = Depends(get_async_session),
    current_user: IamUser = Depends(tenant_user_manage_guard),
) -> dict:
    _validate_tenant_assignable_role(body.role)
    try:
        updated = await update_user_role(
            session,
            tenant_id=current_user.tenant_id,
            user_id=user_id,
            new_role=body.role,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail="User not found") from exc
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc
    await session.flush()
    return {
        "user_id": str(updated.id),
        "role": updated.role.value,
        "updated": True,
    }


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    current_user: IamUser = Depends(tenant_user_manage_guard),
) -> dict:
    try:
        return await offboard_user(
            session=session,
            tenant_id=current_user.tenant_id,
            user_id=user_id,
            offboarded_by=current_user.id,
            reason="Offboarded via /users route",
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail="User not found") from exc
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc


@router.post("/users/{user_id}/offboard", status_code=status.HTTP_200_OK)
async def offboard_user_endpoint(
    user_id: uuid.UUID,
    body: OffboardUserRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(tenant_user_manage_guard),
) -> dict:
    try:
        return await offboard_user(
            session=session,
            tenant_id=user.tenant_id,
            user_id=user_id,
            offboarded_by=user.id,
            reason=body.reason,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail="User not found") from exc
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc
