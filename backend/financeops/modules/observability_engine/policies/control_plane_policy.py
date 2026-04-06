from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends

from financeops.platform.services.enforcement.interceptors import (
    ensure_control_plane_access,
)


def observability_control_plane_dependency(*, action: str, resource_type: str) -> Callable:
    async def _dependency(
        decision: dict = Depends(
            ensure_control_plane_access(
                module_code="observability_engine",
                resource_type=resource_type,
                action=action,
                execution_mode="api",
            )
        ),
    ) -> dict:
        return decision

    return _dependency
