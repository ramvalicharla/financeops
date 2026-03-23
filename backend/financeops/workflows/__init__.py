from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from temporalio.service import ServiceCall


_original_service_call = ServiceCall.__call__


async def _service_call_compat(
    self: ServiceCall[Any, Any],
    req: Any,
    *,
    retry: bool = False,
    metadata: Mapping[str, str] = {},
    timeout: Any = None,
) -> Any:
    # Compatibility shim for SDK callers that pass dict request payloads.
    if isinstance(req, dict):
        req = self.req_type(**req)
    return await _original_service_call(
        self,
        req,
        retry=retry,
        metadata=metadata,
        timeout=timeout,
    )


if not getattr(ServiceCall.__call__, "__financeops_dict_compat__", False):
    ServiceCall.__call__ = _service_call_compat  # type: ignore[assignment]
    setattr(ServiceCall.__call__, "__financeops_dict_compat__", True)
