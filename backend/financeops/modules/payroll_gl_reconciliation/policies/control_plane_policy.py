from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends

from financeops.platform.services.enforcement.interceptors import (
    control_plane_guard,
    require_valid_context_token,
)


def payroll_gl_reconciliation_control_plane_dependency(
    *, action: str, resource_type: str
) -> Callable:
    async def _dependency(
        _: dict = Depends(
            require_valid_context_token(module_code="payroll_gl_reconciliation")
        ),
        __: dict = Depends(
            control_plane_guard(
                module_code="payroll_gl_reconciliation",
                resource_type=resource_type,
                action=action,
                execution_mode="api",
            )
        ),
    ) -> dict:
        return __

    return _dependency

