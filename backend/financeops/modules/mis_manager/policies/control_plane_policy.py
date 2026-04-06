from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends

from financeops.platform.services.enforcement.interceptors import (
    ensure_control_plane_access,
)


def mis_control_plane_dependency(*, action: str, resource_type: str) -> Callable:
    async def _dependency(
        decision: dict = Depends(
            ensure_control_plane_access(
                module_code="mis_manager",
                resource_type=resource_type,
                action=action,
                execution_mode="api",
            )
        ),
    ) -> dict:
        # Guard enforces module, RBAC, quota, and isolation checks.
        return decision

    return _dependency
