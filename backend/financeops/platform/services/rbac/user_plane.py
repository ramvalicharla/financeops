from __future__ import annotations

from enum import Enum

from financeops.db.models.users import UserRole


class TenantRole(str, Enum):
    tenant_viewer = "tenant_viewer"
    tenant_member = "tenant_member"
    tenant_manager = "tenant_manager"
    tenant_admin = "tenant_admin"
    tenant_owner = "tenant_owner"


_TENANT_ROLE_RANK = {
    TenantRole.tenant_viewer: 0,
    TenantRole.tenant_member: 1,
    TenantRole.tenant_manager: 2,
    TenantRole.tenant_admin: 3,
    TenantRole.tenant_owner: 4,
}

_PLATFORM_ONLY_ROLES = {
    UserRole.super_admin,
    UserRole.platform_owner,
    UserRole.platform_admin,
    UserRole.platform_support,
}

_TENANT_ASSIGNABLE_ROLES = {
    UserRole.finance_leader,
    UserRole.finance_team,
    UserRole.director,
    UserRole.entity_user,
    UserRole.auditor,
    UserRole.hr_manager,
    UserRole.employee,
    UserRole.read_only,
}

_TENANT_ROLE_MAP = {
    UserRole.super_admin: TenantRole.tenant_owner,
    UserRole.platform_owner: TenantRole.tenant_owner,
    UserRole.platform_admin: TenantRole.tenant_admin,
    UserRole.finance_leader: TenantRole.tenant_owner,
    UserRole.finance_team: TenantRole.tenant_member,
    UserRole.read_only: TenantRole.tenant_viewer,
    UserRole.director: TenantRole.tenant_manager,
    UserRole.entity_user: TenantRole.tenant_member,
    UserRole.auditor: TenantRole.tenant_viewer,
    UserRole.hr_manager: TenantRole.tenant_manager,
    UserRole.employee: TenantRole.tenant_member,
}


def resolve_tenant_role(user_role: UserRole | str) -> TenantRole | None:
    try:
        normalized = user_role if isinstance(user_role, UserRole) else UserRole(str(user_role))
    except ValueError:
        return None
    return _TENANT_ROLE_MAP.get(normalized)


def has_minimum_tenant_role(
    user_role: UserRole | str,
    minimum_role: TenantRole,
) -> bool:
    effective = resolve_tenant_role(user_role)
    if effective is None:
        return False
    return _TENANT_ROLE_RANK[effective] >= _TENANT_ROLE_RANK[minimum_role]


def is_platform_only_role(user_role: UserRole | str) -> bool:
    try:
        normalized = user_role if isinstance(user_role, UserRole) else UserRole(str(user_role))
    except ValueError:
        return False
    return normalized in _PLATFORM_ONLY_ROLES


def is_tenant_assignable_role(user_role: UserRole | str) -> bool:
    try:
        normalized = user_role if isinstance(user_role, UserRole) else UserRole(str(user_role))
    except ValueError:
        return False
    return normalized in _TENANT_ASSIGNABLE_ROLES

