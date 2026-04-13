"""
Deprecation shim — import directly from financeops.api.deps instead.

All auth and session dependency implementations live in deps.py.
This module re-exports them so any legacy import path continues to work.
"""
from financeops.api.deps import (
    get_async_session,
    get_current_tenant,
    get_current_tenant_id,
    get_current_user,
    get_redis,
    get_session_with_rls,
    get_settings_dep,
    oauth2_scheme,
    require_auditor_or_above,
    require_director,
    require_entitlement,
    require_finance_leader,
    require_finance_team,
    require_mfa,
    require_org_setup,
    require_platform_admin,
    require_platform_owner,
    require_role,
    require_support_or_admin,
    require_tenant_minimum_role,
    require_user_plane_permission,
)

__all__ = [
    "get_async_session",
    "get_current_tenant",
    "get_current_tenant_id",
    "get_current_user",
    "get_redis",
    "get_session_with_rls",
    "get_settings_dep",
    "oauth2_scheme",
    "require_auditor_or_above",
    "require_director",
    "require_entitlement",
    "require_finance_leader",
    "require_finance_team",
    "require_mfa",
    "require_org_setup",
    "require_platform_admin",
    "require_platform_owner",
    "require_role",
    "require_support_or_admin",
    "require_tenant_minimum_role",
    "require_user_plane_permission",
]
