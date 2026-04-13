"""
Shared platform-identity helpers.

All platform tenant / role checks must go through this module.
Local copies in individual routers have been removed.
"""
from __future__ import annotations

import uuid

from financeops.core.exceptions import AuthorizationError
from financeops.db.models.users import IamUser, UserRole

# The sentinel UUID that identifies the platform tenant (all bits zero).
PLATFORM_TENANT_ID: uuid.UUID = uuid.UUID(int=0)

_PLATFORM_ROLES: frozenset[UserRole] = frozenset(
    {
        UserRole.platform_owner,
        UserRole.platform_admin,
        UserRole.platform_support,
        UserRole.super_admin,
    }
)

_PLATFORM_OWNER_ROLES: frozenset[UserRole] = frozenset(
    {
        UserRole.platform_owner,
        UserRole.super_admin,
    }
)


def _role_value(role: UserRole | str) -> str:
    return role.value if isinstance(role, UserRole) else str(role)


def is_platform_user(user: IamUser) -> bool:
    """Return True iff the user belongs to the platform tenant and holds a platform role."""
    return (
        user.tenant_id == PLATFORM_TENANT_ID
        and _role_value(user.role) in {item.value for item in _PLATFORM_ROLES}
    )


def require_platform_user(user: IamUser) -> IamUser:
    """Raise AuthorizationError unless the user is a platform user."""
    if not is_platform_user(user):
        raise AuthorizationError("platform role required")
    return user


def require_platform_owner(user: IamUser) -> IamUser:
    """Raise AuthorizationError unless the user is a platform owner (or super_admin)."""
    if (
        user.tenant_id != PLATFORM_TENANT_ID
        or _role_value(user.role) not in {item.value for item in _PLATFORM_OWNER_ROLES}
    ):
        raise AuthorizationError("platform_owner role required")
    return user
