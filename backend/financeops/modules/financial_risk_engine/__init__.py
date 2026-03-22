from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends

from financeops.platform.services.enforcement.interceptors import (
    control_plane_guard,
    require_valid_context_token,
)


def financial_risk_control_plane_dependency(*, action: str, resource_type: str) -> Callable:
    async def _dependency(
        _: dict = Depends(require_valid_context_token(module_code="financial_risk_engine")),
        __: dict = Depends(
            control_plane_guard(
                module_code="financial_risk_engine",
                resource_type=resource_type,
                action=action,
                execution_mode="api",
            )
        ),
    ) -> dict:
        return __

    return _dependency
