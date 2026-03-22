from __future__ import annotations

from typing import Any

from financeops.config import get_settings
from financeops.core.exceptions import FeatureNotImplementedError


class ConnectionService:
    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        _ = kwargs
        if not get_settings().ERP_CONNECTION_SERVICE_ENABLED:
            raise FeatureNotImplementedError("erp_connection_service")
        raise FeatureNotImplementedError("erp_connection_service")
