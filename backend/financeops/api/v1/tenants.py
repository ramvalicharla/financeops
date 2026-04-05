from __future__ import annotations

import hashlib
import logging
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import (
    get_async_session,
    get_current_user,
    require_finance_leader,
)
from financeops.config import settings
from financeops.db.models.tenants import IamTenant
from financeops.db.models.users import IamUser, UserRole
from financeops.modules.notifications.channels.email_channel import send_direct
from financeops.modules.notifications.templates.emails import user_invited_email
from financeops.platform.db.models.user_membership import CpUserEntityAssignment
from financeops.services.credit_service import get_balance
from financeops.services.tenant_service import (
    get_tenant,
    list_workspaces,
    update_tenant_settings,
)
from financeops.services.user_service import (
    deactivate_user,
    list_tenant_users,
    normalize_email,
    update_user_role,
)
from financeops.utils.display_scale import (
    DisplayScale,
    SCALE_FULL_LABELS,
    get_effective_scale,
)
from financeops.utils.gstin import extract_state_code, validate_gstin, validate_pan

log = logging.getLogger(__name__)
router = APIRouter()


class UpdateTenantRequest(BaseModel):
    display_name: str | None = None
    timezone: str | None = None
    pan: str | None = None
    gstin: str | None = None
    state_code: str | None = None


class InviteUserRequest(BaseModel):
    email: EmailStr
    full_name: str
    role: UserRole
    entity_ids: list[uuid.UUID] = []


class UpdateRoleRequest(BaseModel):
    role: UserRole


class UpdateDisplayPreferencesRequest(BaseModel):
    user_scale: str | None = None
    tenant_scale: str | None = None


@router.get("/me")
async def get_my_tenant(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    tenant = await get_tenant(session, user.tenant_id)
    workspaces = await list_workspaces(session, user.tenant_id)
    return {
        "tenant_id": str(tenant.id),
        "display_name": tenant.display_name,
        "tenant_type": tenant.tenant_type.value,
        "country": tenant.country,
        "timezone": tenant.timezone,
        "pan": tenant.pan,
        "gstin": tenant.gstin,
        "state_code": tenant.state_code,
        "status": tenant.status.value,
        "org_setup_complete": tenant.org_setup_complete,
        "org_setup_step": tenant.org_setup_step,
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
    if body.pan is not None and body.pan.strip() and not validate_pan(body.pan):
        raise HTTPException(status_code=422, detail="Invalid PAN")
    gstin_value: str | None = None
    state_code_value = body.state_code
    if body.gstin is not None:
        gstin_value = body.gstin.strip().upper()
        if gstin_value and not validate_gstin(gstin_value):
            raise HTTPException(status_code=422, detail="Invalid GSTIN")
        if gstin_value:
            state_code_value = extract_state_code(gstin_value)

    tenant = await get_tenant(session, user.tenant_id)
    await update_tenant_settings(
        session,
        tenant=tenant,
        actor_user_id=user.id,
        display_name=body.display_name,
        timezone_str=body.timezone,
        pan=(body.pan.strip().upper() if body.pan else None),
        gstin=gstin_value,
        state_code=state_code_value,
    )
    await session.flush()
    return {"tenant_id": str(tenant.id), "updated": True}


@router.get("/me/users")
async def list_my_users(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(require_finance_leader),
) -> dict:
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
    tenant = await get_tenant(session, user.tenant_id)
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
        full_name=body.full_name,
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
    subject, html = user_invited_email(
        invitee_name=body.full_name,
        inviter_name=user.full_name,
        company_name=tenant.display_name,
        invite_url=invite_url,
        unsubscribe_url=f"{frontend_base}/settings/privacy",
    )
    await send_direct(
        to=body.email,
        subject=subject,
        html_body=html,
        text_body=f"You are invited to FinanceOps. Accept invitation: {invite_url}",
    )

    await session.flush()
    return {
        "user_id": str(new_user.id),
        "email": new_user.email,
        "role": new_user.role.value,
        "message": f"Invitation sent to {new_user.email}",
    }


@router.patch("/me/users/{user_id}")
async def update_user(
    user_id: uuid.UUID,
    body: UpdateRoleRequest,
    session: AsyncSession = Depends(get_async_session),
    current_user: IamUser = Depends(require_finance_leader),
) -> dict:
    _ = current_user
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
    _ = current_user
    deactivated = await deactivate_user(session, user_id)
    await session.flush()
    return {"user_id": str(deactivated.id), "deactivated": True}


@router.get("/me/credits")
async def get_credits(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    from sqlalchemy import desc, select

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


@router.get("/display-preferences")
async def get_display_preferences(
    session: AsyncSession = Depends(get_async_session),
    current_user: IamUser = Depends(get_current_user),
) -> dict:
    tenant = await session.get(IamTenant, current_user.tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    effective = get_effective_scale(
        current_user.display_scale_override,
        tenant.default_display_scale,
    )
    return {
        "effective_scale": effective.value,
        "user_override": current_user.display_scale_override,
        "tenant_default": tenant.default_display_scale,
        "currency": tenant.default_currency,
        "locale": tenant.number_format_locale,
        "scale_label": SCALE_FULL_LABELS[effective],
    }


@router.patch("/display-preferences")
async def update_display_preferences(
    body: UpdateDisplayPreferencesRequest,
    session: AsyncSession = Depends(get_async_session),
    current_user: IamUser = Depends(get_current_user),
) -> dict:
    if body.user_scale is not None:
        current_user.display_scale_override = DisplayScale(body.user_scale).value

    if body.tenant_scale is not None:
        if current_user.role not in {UserRole.finance_leader, UserRole.platform_owner}:
            raise HTTPException(
                status_code=403,
                detail="Finance Leader role required to set tenant default",
            )
        tenant = await session.get(IamTenant, current_user.tenant_id)
        if tenant is None:
            raise HTTPException(status_code=404, detail="Tenant not found")
        tenant.default_display_scale = DisplayScale(body.tenant_scale).value

    await session.flush()
    return {"message": "Display preferences updated"}
