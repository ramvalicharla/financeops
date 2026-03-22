from __future__ import annotations

from typing import Any

from financeops.config import get_settings
from financeops.core.exceptions import FeatureNotImplementedError


class ConnectorVersionService:
    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        _ = kwargs
        if not get_settings().ERP_CONNECTOR_VERSIONING_ENABLED:
            raise FeatureNotImplementedError("erp_connector_versioning")
        raise FeatureNotImplementedError("erp_connector_versioning")
