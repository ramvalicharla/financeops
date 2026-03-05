from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import NotFoundError, ValidationError
from financeops.core.security import hash_password
from financeops.db.models.users import IamUser, UserRole

log = logging.getLogger(__name__)


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
    existing = await session.execute(
        select(IamUser).where(IamUser.email == email.lower().strip())
    )
    if existing.scalar_one_or_none() is not None:
        raise ValidationError(f"Email {email} is already registered")

    user = IamUser(
        tenant_id=tenant_id,
        email=email.lower().strip(),
        hashed_password=hash_password(password),
        full_name=full_name,
        role=role,
        is_active=True,
        mfa_enabled=False,
    )
    session.add(user)
    await session.flush()
    log.info("User created: id=%s email=%s tenant=%s", user.id, email, str(tenant_id)[:8])
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
    result = await session.execute(
        select(IamUser).where(IamUser.email == email.lower().strip())
    )
    return result.scalar_one_or_none()


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


async def deactivate_user(session: AsyncSession, user_id: uuid.UUID) -> IamUser:
    """Soft-delete a user by setting is_active=False."""
    user = await get_user_by_id(session, user_id)
    user.is_active = False
    await session.flush()
    log.info("User deactivated: id=%s", user_id)
    return user


async def update_user_role(
    session: AsyncSession,
    user_id: uuid.UUID,
    new_role: UserRole,
) -> IamUser:
    """Update a user's role."""
    user = await get_user_by_id(session, user_id)
    user.role = new_role
    await session.flush()
    return user
