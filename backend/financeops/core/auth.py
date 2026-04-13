"""
Deprecation shim — import directly from financeops.api.deps instead.

All auth dependency implementations live in deps.py.
This module re-exports them so any legacy import path continues to work.
"""
from financeops.api.deps import (
    get_current_tenant_id,
    get_current_user,
    require_mfa,
    require_role,
)

__all__ = [
    "get_current_tenant_id",
    "get_current_user",
    "require_mfa",
    "require_role",
]
