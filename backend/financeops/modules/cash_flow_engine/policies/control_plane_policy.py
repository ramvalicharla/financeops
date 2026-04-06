from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends

from financeops.platform.services.enforcement.interceptors import (
    ensure_module_governance,
)


def cash_flow_control_plane_dependency(*, action: str, resource_type: str) -> Callable:
    async def _dependency(
        decision: dict = Depends(
            ensure_module_governance(
                module_code="cash_flow_engine",
                resource_type=resource_type,
                action=action,
                execution_mode="api",
            )
        ),
    ) -> dict:
        return decision

    return _dependency
