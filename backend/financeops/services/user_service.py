from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import NotFoundError, ValidationError
from financeops.core.security import hash_password
from financeops.db.models.users import IamSession, IamUser, UserRole
from financeops.platform.services.rbac.user_plane import is_tenant_assignable_role
from financeops.services.audit_service import log_action
from financeops.services.audit_writer import AuditEvent, AuditWriter

log = logging.getLogger(__name__)


def normalize_email(email: str) -> str:
    """Return the canonical email form used across auth and user creation."""
    return email.strip().lower()


async def create_user(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    email: str,
    password: str,
    full_name: str,
    role: UserRole = UserRole.read_only,
) -> IamUser:
    """Create a new user. Raises ValidationError if email already exists."""
    normalized_email = normalize_email(email)
    existing = await session.execute(
        select(IamUser).where(func.lower(IamUser.email) == normalized_email)
    )
    if existing.scalar_one_or_none() is not None:
        raise ValidationError(f"Email {email} is already registered")

    user = await AuditWriter.insert_record(
        session,
        record=IamUser(
            tenant_id=tenant_id,
            email=normalized_email,
            hashed_password=hash_password(password),
            full_name=full_name,
            role=role,
            is_active=True,
            mfa_enabled=False,
            force_mfa_setup=True,
        ),
        audit=AuditEvent(
            tenant_id=tenant_id,
            action="user.created",
            resource_type="user",
            resource_name=normalized_email,
            new_value={"role": role.value, "full_name": full_name},
        ),
    )
    log.info(
        "User created: id=%s email=%s tenant=%s", user.id, email, str(tenant_id)[:8]
    )
    return user


async def get_user_by_id(session: AsyncSession, user_id: uuid.UUID) -> IamUser:
    """Return user by UUID or raise NotFoundError."""
    result = await session.execute(select(IamUser).where(IamUser.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise NotFoundError(f"User {user_id} not found")
    return user


async def get_user_by_email(session: AsyncSession, email: str) -> IamUser | None:
    """Return user by email (case-insensitive), or None if not found."""
    normalized_email = normalize_email(email)
    result = await session.execute(
        select(IamUser)
        .where(func.lower(IamUser.email) == normalized_email)
        .order_by(IamUser.created_at.asc(), IamUser.id.asc())
        .limit(2)
    )
    rows = list(result.scalars().all())
    if len(rows) > 1:
        log.error("Duplicate normalized emails found for %s", normalized_email)
        return None
    return rows[0] if rows else None


async def list_tenant_users(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
) -> list[IamUser]:
    """List active users for a tenant with pagination."""
    result = await session.execute(
        select(IamUser)
        .where(IamUser.tenant_id == tenant_id)
        .order_by(IamUser.created_at)
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def deactivate_user(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
) -> IamUser:
    """Soft-delete a user by setting is_active=False."""
    result = await session.execute(
        select(IamUser).where(
            IamUser.id == user_id,
            IamUser.tenant_id == tenant_id,
        )
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise NotFoundError(f"User {user_id} not found in tenant {tenant_id}")
    old_state = {"is_active": user.is_active}
    user.is_active = False
    await AuditWriter.flush_with_audit(
        session,
        audit=AuditEvent(
            tenant_id=user.tenant_id,
            user_id=user.id,
            action="user.deactivated",
            resource_type="user",
            resource_id=str(user.id),
            resource_name=user.email,
            old_value=old_state,
            new_value={"is_active": user.is_active},
        ),
    )
    log.info("User deactivated: id=%s", user_id)
    return user


async def update_user_role(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    new_role: UserRole,
) -> IamUser:
    """Update a user's role."""
    if not is_tenant_assignable_role(new_role):
        raise ValidationError("Platform roles cannot be assigned from tenant user management")
    result = await session.execute(
        select(IamUser).where(
            IamUser.id == user_id,
            IamUser.tenant_id == tenant_id,
        )
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise NotFoundError(f"User {user_id} not found in tenant {tenant_id}")
    old_state = {"role": user.role.value}
    user.role = new_role
    await AuditWriter.flush_with_audit(
        session,
        audit=AuditEvent(
            tenant_id=user.tenant_id,
            user_id=user.id,
            action="user.role.updated",
            resource_type="user",
            resource_id=str(user.id),
            resource_name=user.email,
            old_value=old_state,
            new_value={"role": new_role.value},
        ),
    )
    return user


async def offboard_user(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    offboarded_by: uuid.UUID,
    reason: str,
) -> dict:
    """
    Atomically offboard a user. All or nothing.
    """
    user_result = await session.execute(
        select(IamUser).where(
            IamUser.id == user_id,
            IamUser.tenant_id == tenant_id,
        )
    )
    user = user_result.scalar_one_or_none()
    if user is None:
        raise NotFoundError(f"User {user_id} not found in tenant {tenant_id}")
    if not user.is_active:
        raise ValidationError(f"User {user_id} is already inactive")

    sessions_result = await session.execute(
        delete(IamSession)
        .where(IamSession.user_id == user_id)
        .returning(IamSession.id)
    )
    sessions_revoked = len(list(sessions_result.fetchall()))

    grants_revoked = 0
    try:
        from financeops.db.models.auditor import AuditorGrant

        grants_result = await session.execute(
            delete(AuditorGrant)
            .where(AuditorGrant.user_id == user_id)
            .returning(AuditorGrant.id)
        )
        grants_revoked = len(list(grants_result.fetchall()))
    except Exception:
        grants_revoked = 0

    await session.execute(
        update(IamUser)
        .where(
            IamUser.id == user_id,
            IamUser.tenant_id == tenant_id,
        )
        .values(
            is_active=False,
            mfa_enabled=False,
            totp_secret_encrypted=None,
        )
    )

    await log_action(
        session,
        tenant_id=tenant_id,
        user_id=offboarded_by,
        action="user.offboarded",
        resource_type="user",
        resource_id=str(user_id),
        resource_name=user.email,
        new_value={
            "reason": reason,
            "sessions_revoked": sessions_revoked,
            "grants_revoked": grants_revoked,
        },
    )
    await session.commit()
    return {
        "user_id": str(user_id),
        "offboarded_at": datetime.now(UTC).isoformat(),
        "sessions_revoked": sessions_revoked,
        "grants_revoked": grants_revoked,
    }

