from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from financeops.modules.erp_sync.domain.enums import ConnectorType, DatasetType
from financeops.modules.erp_sync.infrastructure.connectors.base import (
    AbstractConnector,
    ConnectorCapabilityNotSupported,
    ExtractionError,
)
from financeops.modules.erp_sync.infrastructure.secret_store import SecretStore


def _to_decimal_if_numeric(value: Any) -> Any:
    if isinstance(value, str):
        cleaned = value.strip().replace(",", "")
        if cleaned and all(ch.isdigit() or ch in {"-", "."} for ch in cleaned):
            try:
                return Decimal(cleaned)
            except (InvalidOperation, ValueError):
                return value
    return value


def _normalize_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _normalize_payload(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_normalize_payload(item) for item in value]
    return _to_decimal_if_numeric(value)


class KekaConnector(AbstractConnector):
    connector_type = ConnectorType.KEKA
    connector_version = "4e.1.0"
    supports_resumable_extraction = True
    supported_datasets = {
        DatasetType.PAYROLL_SUMMARY,
        DatasetType.EXPENSE_CLAIMS,
        DatasetType.STAFF_ADVANCES,
    }

    _DATASET_ENDPOINTS: dict[DatasetType, str] = {
        DatasetType.PAYROLL_SUMMARY: "payroll/runs",
        DatasetType.EXPENSE_CLAIMS: "expenses/claims",
        DatasetType.STAFF_ADVANCES: "employees/advances",
    }

    def __init__(self, *, secret_store: SecretStore | None = None) -> None:
        self._secret_store = secret_store or SecretStore()

    async def test_connection(self, credentials: dict[str, Any]) -> dict[str, Any]:
        resolved = await self._resolve_credentials(credentials=credentials)
        payload = await self._request_json(
            resolved,
            endpoint="employees",
            params={"pageNumber": 1, "pageSize": 1},
        )
        return {"ok": True, "connector_type": self.connector_type.value, "payload": payload}

    async def extract(self, dataset_type: DatasetType, **kwargs: Any) -> dict[str, Any]:
        if dataset_type not in self.supported_datasets:
            raise ConnectorCapabilityNotSupported(self.connector_type, dataset_type)
        if not kwargs:
            raise ConnectorCapabilityNotSupported(self.connector_type, dataset_type)
        resolved = await self._resolve_credentials(
            credentials=kwargs.get("credentials"),
            secret_ref=kwargs.get("secret_ref"),
            extra=kwargs,
        )
        checkpoint = kwargs.get("checkpoint") or {}
        page = int(checkpoint.get("page") or kwargs.get("page") or 1)
        page_size = int(checkpoint.get("page_size") or kwargs.get("page_size") or 100)
        payload = await self._request_json(
            resolved,
            endpoint=self._DATASET_ENDPOINTS[dataset_type],
            params={"pageNumber": page, "pageSize": page_size},
        )
        normalized = _normalize_payload(payload)
        records = self._extract_records(normalized)
        next_checkpoint = {"page": page + 1, "page_size": page_size} if len(records) >= page_size else None
        return {
            "dataset_type": dataset_type.value,
            "raw_data": normalized,
            "records": records,
            "line_count": len(records),
            "erp_reported_line_count": len(records),
            "is_resumable": True,
            "next_checkpoint": next_checkpoint,
        }

    async def _resolve_credentials(
        self,
        *,
        credentials: dict[str, Any] | None = None,
        secret_ref: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        resolved = dict(credentials or {})
        if not resolved and secret_ref:
            secret_payload = await self._secret_store.get_secret(secret_ref)
            if isinstance(secret_payload, dict):
                resolved.update(secret_payload)
        if extra:
            for key in ("api_key", "base_url"):
                if key in extra and extra[key] is not None:
                    resolved[key] = extra[key]
        resolved.setdefault("base_url", "https://api.keka.com")
        if not resolved.get("api_key"):
            raise ExtractionError("Keka api_key is required")
        return resolved

    async def _request_json(self, credentials: dict[str, Any], *, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        url = f"{str(credentials['base_url']).rstrip('/')}/{endpoint.lstrip('/')}"
        headers = {"Authorization": f"Bearer {credentials['api_key']}", "Accept": "application/json"}
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.get(url, headers=headers, params=params)
        if response.status_code >= 400:
            raise ExtractionError(f"Keka API error {response.status_code} for {endpoint}")
        payload = response.json()
        if not isinstance(payload, dict):
            raise ExtractionError("Keka API returned non-object payload")
        return payload

    @staticmethod
    def _extract_records(payload: Any) -> list[dict[str, Any]]:
        if not isinstance(payload, dict):
            return []
        for key in ("data", "items", "results", "records"):
            value = payload.get(key)
            if isinstance(value, list):
                return [row for row in value if isinstance(row, dict)]
        return []
