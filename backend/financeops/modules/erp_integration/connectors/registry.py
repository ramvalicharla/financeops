from __future__ import annotations

import uuid
from collections.abc import Mapping
from typing import Any

from financeops.core.exceptions import ValidationError
from financeops.modules.erp_integration.connectors.base import BaseConnector
from financeops.modules.erp_sync.domain.enums import ConnectorType, DatasetType
from financeops.modules.erp_sync.infrastructure.connectors.registry import (
    get_connector as get_legacy_connector,
)


def _to_connector_type(erp_type: str) -> ConnectorType:
    normalized = erp_type.strip().upper()
    mapped = normalized.replace("-", "_")
    try:
        return ConnectorType[mapped]
    except KeyError:
        return ConnectorType(normalized.lower())


def _unwrap_rows(payload: Any, candidate_keys: tuple[str, ...]) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in candidate_keys:
            value = payload.get(key)
            if isinstance(value, list):
                return [row for row in value if isinstance(row, dict)]
    return []


class LegacyConnectorAdapter(BaseConnector):
    def __init__(self, erp_type: str) -> None:
        self._erp_type = erp_type
        self._connector = get_legacy_connector(_to_connector_type(erp_type))

    async def authenticate(self, *, connection_config: Mapping[str, Any]) -> dict[str, Any]:
        credentials = dict(connection_config.get("credentials", {})) if isinstance(connection_config, dict) else {}
        result = await self._connector.test_connection(credentials)
        return {"ok": True, "result": result}

    async def fetch_chart_of_accounts(
        self,
        *,
        connection_config: Mapping[str, Any],
    ) -> list[dict[str, Any]]:
        payload = await self._connector.extract(
            DatasetType.CHART_OF_ACCOUNTS,
            **dict(connection_config),
        )
        rows = _unwrap_rows(payload, ("accounts", "rows", "data", "items"))
        return rows

    async def fetch_transactions(
        self,
        *,
        connection_config: Mapping[str, Any],
    ) -> list[dict[str, Any]]:
        payload = await self._connector.extract(
            DatasetType.GENERAL_LEDGER,
            **dict(connection_config),
        )
        rows = _unwrap_rows(payload, ("transactions", "journals", "rows", "data", "items", "lines"))
        return rows

    async def push_journal(
        self,
        *,
        connection_config: Mapping[str, Any],
        journal_payload: Mapping[str, Any],
    ) -> dict[str, Any]:
        push_method = getattr(self._connector, "push_journal", None)
        if callable(push_method):
            response = await push_method(journal_payload=journal_payload, **dict(connection_config))
            if isinstance(response, dict):
                return response
        external_id = str(journal_payload.get("external_reference_id") or f"{self._erp_type}-{uuid.uuid4()}")
        return {"status": "accepted", "erp_journal_id": external_id}

    async def fetch_vendors(
        self,
        *,
        connection_config: Mapping[str, Any],
    ) -> list[dict[str, Any]]:
        payload = await self._connector.extract(
            DatasetType.VENDOR_MASTER,
            **dict(connection_config),
        )
        return _unwrap_rows(payload, ("vendors", "rows", "data", "items"))

    async def fetch_customers(
        self,
        *,
        connection_config: Mapping[str, Any],
    ) -> list[dict[str, Any]]:
        payload = await self._connector.extract(
            DatasetType.CUSTOMER_MASTER,
            **dict(connection_config),
        )
        return _unwrap_rows(payload, ("customers", "rows", "data", "items"))


class ManualConnector(BaseConnector):
    async def authenticate(self, *, connection_config: Mapping[str, Any]) -> dict[str, Any]:
        return {"ok": True, "mode": "MANUAL"}

    async def fetch_chart_of_accounts(
        self,
        *,
        connection_config: Mapping[str, Any],
    ) -> list[dict[str, Any]]:
        rows = connection_config.get("chart_of_accounts", [])
        return rows if isinstance(rows, list) else []

    async def fetch_transactions(
        self,
        *,
        connection_config: Mapping[str, Any],
    ) -> list[dict[str, Any]]:
        rows = connection_config.get("transactions", [])
        return rows if isinstance(rows, list) else []

    async def push_journal(
        self,
        *,
        connection_config: Mapping[str, Any],
        journal_payload: Mapping[str, Any],
    ) -> dict[str, Any]:
        external_id = str(journal_payload.get("external_reference_id") or f"MANUAL-{uuid.uuid4()}")
        return {"status": "accepted", "erp_journal_id": external_id}

    async def fetch_vendors(
        self,
        *,
        connection_config: Mapping[str, Any],
    ) -> list[dict[str, Any]]:
        rows = connection_config.get("vendors", [])
        return rows if isinstance(rows, list) else []

    async def fetch_customers(
        self,
        *,
        connection_config: Mapping[str, Any],
    ) -> list[dict[str, Any]]:
        rows = connection_config.get("customers", [])
        return rows if isinstance(rows, list) else []


CONNECTOR_REGISTRY: dict[str, type[BaseConnector]] = {
    "MANUAL": ManualConnector,
}


def get_connector(erp_type: str) -> BaseConnector:
    normalized = erp_type.strip().upper()
    connector_cls = CONNECTOR_REGISTRY.get(normalized)
    if connector_cls is not None:
        return connector_cls()
    try:
        _to_connector_type(normalized)
    except Exception as exc:
        raise ValidationError(f"Unsupported erp_type '{erp_type}'.") from exc
    return LegacyConnectorAdapter(normalized)
