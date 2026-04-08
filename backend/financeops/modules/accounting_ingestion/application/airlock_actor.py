from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import ValidationError
from financeops.core.governance.airlock import AirlockActor
from financeops.db.models.users import IamUser, UserRole

_PREFERRED_AIRLOCK_ROLES: tuple[UserRole, ...] = (
    UserRole.finance_leader,
    UserRole.finance_team,
    UserRole.platform_admin,
    UserRole.platform_owner,
    UserRole.super_admin,
)


async def resolve_airlock_actor(db: AsyncSession, *, tenant_id: uuid.UUID) -> AirlockActor:
    for role in _PREFERRED_AIRLOCK_ROLES:
        user = (
            await db.execute(
                select(IamUser).where(
                    IamUser.tenant_id == tenant_id,
                    IamUser.role == role,
                    IamUser.is_active.is_(True),
                )
            )
        ).scalars().first()
        if user is not None:
            return AirlockActor(user_id=user.id, tenant_id=tenant_id, role=user.role.value)
    raise ValidationError("No active tenant governance user is available for airlock admission.")
