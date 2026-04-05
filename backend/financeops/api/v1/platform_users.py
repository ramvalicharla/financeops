from __future__ import annotations

import asyncio
import logging
import secrets
import smtplib
import uuid
from email.message import EmailMessage

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user
from financeops.config import settings
from financeops.core.security import hash_password
from financeops.db.models.users import IamUser, UserRole
from financeops.services.audit_service import log_action
from financeops.services.user_service import normalize_email
from financeops.shared_kernel.pagination import Paginated

log = logging.getLogger(__name__)

router = APIRouter(prefix="/platform/users", tags=["platform-users"])

PLATFORM_TENANT_ID = uuid.UUID(int=0)
_PLATFORM_OWNER_ROLES = {UserRole.platform_owner, UserRole.super_admin}
_PLATFORM_ROLES = {
    UserRole.platform_owner,
    UserRole.platform_admin,
    UserRole.platform_support,
    UserRole.super_admin,
}


def _role_value(role: UserRole | str) -> str:
    return role.value if isinstance(role, UserRole) else str(role)


class CreatePlatformUserRequest(BaseModel):
    email: EmailStr
    full_name: str
    role: UserRole
    send_invite: bool = True


class UpdatePlatformRoleRequest(BaseModel):
    role: UserRole


def _is_platform_user(user: IamUser) -> bool:
    return (
        user.tenant_id == PLATFORM_TENANT_ID
        and _role_value(user.role) in {item.value for item in _PLATFORM_ROLES}
    )


def _require_platform_owner(user: IamUser) -> IamUser:
    if (
        user.tenant_id != PLATFORM_TENANT_ID
        or _role_value(user.role) not in {item.value for item in _PLATFORM_OWNER_ROLES}
    ):
        raise HTTPException(status_code=403, detail="platform_owner role required")
    return user


def _require_platform_user(user: IamUser) -> IamUser:
    if not _is_platform_user(user):
        raise HTTPException(status_code=403, detail="platform role required")
    return user


def _smtp_configured() -> bool:
    host = str(settings.SMTP_HOST or "").strip()
    user = str(settings.SMTP_USER or "").strip()
    password = str(settings.SMTP_PASSWORD or "").strip()
    if not settings.SMTP_REQUIRED:
        return False
    if not host or host.lower() == "localhost":
        return False
    return bool(user and password)


def _send_invite_email_sync(email: str, full_name: str, temp_password: str) -> None:
    message = EmailMessage()
    message["From"] = settings.SMTP_USER or "no-reply@financeops.local"
    message["To"] = email
    message["Subject"] = "FinanceOps Platform Access"
    message.set_content(
        "\n".join(
            [
                f"Hi {full_name},",
                "",
                "Your platform account has been created.",
                f"Temporary password: {temp_password}",
                "You must set up MFA on first login.",
            ]
        )
    )
    with smtplib.SMTP(
        host=settings.SMTP_HOST,
        port=int(settings.SMTP_PORT),
        timeout=30,
    ) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()
        smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        smtp.send_message(message)


def _serialize_user(row: IamUser) -> dict[str, str | bool]:
    return {
        "id": str(row.id),
        "tenant_id": str(row.tenant_id),
        "email": row.email,
        "full_name": row.full_name,
        "role": _role_value(row.role),
        "is_active": row.is_active,
        "mfa_enabled": row.mfa_enabled,
        "force_mfa_setup": row.force_mfa_setup,
        "created_at": row.created_at.isoformat(),
    }


async def _get_platform_user_or_404(
    session: AsyncSession,
    user_id: uuid.UUID,
) -> IamUser:
    row = (
        await session.execute(
            select(IamUser).where(
                IamUser.id == user_id,
                IamUser.tenant_id == PLATFORM_TENANT_ID,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="platform user not found")
    return row


async def _active_platform_owner_count(session: AsyncSession) -> int:
    return int(
        (
            await session.execute(
                select(func.count())
                .select_from(IamUser)
                .where(
                    IamUser.tenant_id == PLATFORM_TENANT_ID,
                    IamUser.role == UserRole.platform_owner,
                    IamUser.is_active.is_(True),
                )
            )
        ).scalar_one()
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_platform_user(
    request: Request,
    body: CreatePlatformUserRequest,
    session: AsyncSession = Depends(get_async_session),
    current_user: IamUser = Depends(get_current_user),
) -> dict:
    _require_platform_owner(current_user)
    normalized_email = normalize_email(body.email)
    if _role_value(body.role) not in {
        UserRole.platform_admin.value,
        UserRole.platform_support.value,
    }:
        raise HTTPException(status_code=422, detail="role must be platform_admin or platform_support")

    existing = (
        await session.execute(
            select(IamUser).where(IamUser.email == normalized_email)
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=422, detail="email already exists")

    temp_password = secrets.token_urlsafe(12)
    user = IamUser(
        tenant_id=PLATFORM_TENANT_ID,
        email=normalized_email,
        hashed_password=hash_password(temp_password),
        full_name=body.full_name.strip(),
        role=body.role,
        is_active=True,
        mfa_enabled=False,
        force_mfa_setup=True,
    )
    session.add(user)
    await session.flush()

    response = _serialize_user(user)
    if body.send_invite:
        if _smtp_configured():
            try:
                await asyncio.to_thread(
                    _send_invite_email_sync,
                    user.email,
                    user.full_name,
                    temp_password,
                )
            except Exception:
                log.warning("platform invite email failed for %s", user.email, exc_info=True)
                response["temp_password"] = temp_password
        else:
            log.warning("SMTP not configured; returning temporary password for platform user invite")
            response["temp_password"] = temp_password
    await log_action(
        session,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        action="platform.user.created",
        resource_type="iam_user",
        resource_id=str(user.id),
        resource_name=user.email,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await session.flush()
    return response


@router.get("", response_model=Paginated[dict])
async def list_platform_users(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    current_user: IamUser = Depends(get_current_user),
) -> Paginated[dict]:
    _require_platform_owner(current_user)
    base_stmt = select(IamUser).where(IamUser.tenant_id == PLATFORM_TENANT_ID)
    total = int(
        (
            await session.execute(
                select(func.count()).select_from(base_stmt.subquery())
            )
        ).scalar_one()
    )
    rows = (
        await session.execute(
            base_stmt.order_by(IamUser.created_at.asc()).offset(offset).limit(limit)
        )
    ).scalars().all()
    return Paginated[dict](
        data=[_serialize_user(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/me")
async def get_platform_me(
    current_user: IamUser = Depends(get_current_user),
) -> dict:
    _require_platform_user(current_user)
    return _serialize_user(current_user)


@router.patch("/{user_id}/role")
async def update_platform_role(
    request: Request,
    user_id: uuid.UUID,
    body: UpdatePlatformRoleRequest,
    session: AsyncSession = Depends(get_async_session),
    current_user: IamUser = Depends(get_current_user),
) -> dict:
    _require_platform_owner(current_user)
    if user_id == current_user.id:
        raise HTTPException(status_code=422, detail="cannot change own role")

    row = await _get_platform_user_or_404(session, user_id)
    owner_count = await _active_platform_owner_count(session)
    if (
        _role_value(row.role) == UserRole.platform_owner.value
        and _role_value(body.role) != UserRole.platform_owner.value
        and owner_count <= 1
    ):
        raise HTTPException(status_code=422, detail="cannot demote last platform_owner")

    previous_role = _role_value(row.role)
    row.role = body.role
    await log_action(
        session,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        action="platform.user.role_updated",
        resource_type="iam_user",
        resource_id=str(row.id),
        resource_name=row.email,
        old_value={"role": previous_role},
        new_value={"role": _role_value(row.role)},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await session.flush()
    return _serialize_user(row)


@router.delete("/{user_id}")
async def deactivate_platform_user(
    request: Request,
    user_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    current_user: IamUser = Depends(get_current_user),
) -> dict:
    _require_platform_owner(current_user)
    if user_id == current_user.id:
        raise HTTPException(status_code=422, detail="cannot deactivate yourself")

    row = await _get_platform_user_or_404(session, user_id)
    owner_count = await _active_platform_owner_count(session)
    if _role_value(row.role) == UserRole.platform_owner.value and row.is_active and owner_count <= 1:
        raise HTTPException(status_code=422, detail="cannot deactivate last platform_owner")

    row.is_active = False
    await log_action(
        session,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        action="platform.user.deactivated",
        resource_type="iam_user",
        resource_id=str(row.id),
        resource_name=row.email,
        old_value={"is_active": True},
        new_value={"is_active": False},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await session.flush()
    return _serialize_user(row)
