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


def _to_decimal(value: Any) -> Decimal | None:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, str):
        cleaned = value.strip().replace(",", "")
        if cleaned and all(ch.isdigit() or ch in {"-", "."} for ch in cleaned):
            try:
                return Decimal(cleaned)
            except (InvalidOperation, ValueError):
                return None
    return None


def _normalize_payload(value: Any, *, parent_key: str | None = None) -> Any:
    if isinstance(value, dict):
        normalized: dict[str, Any] = {}
        for key, item in value.items():
            normalized[key] = _normalize_payload(item, parent_key=key.lower())
        return normalized
    if isinstance(value, list):
        return [_normalize_payload(item, parent_key=parent_key) for item in value]
    if parent_key and "amount" in parent_key:
        amount = _to_decimal(value)
        if amount is not None:
            return (amount / Decimal("100")).quantize(Decimal("0.01"))
    return value


class RazorpayPayrollConnector(AbstractConnector):
    connector_type = ConnectorType.RAZORPAY_PAYROLL
    connector_version = "4e.1.0"
    supports_resumable_extraction = False
    supported_datasets = {
        DatasetType.PAYROLL_SUMMARY,
        DatasetType.STAFF_ADVANCES,
    }

    _DATASET_ENDPOINTS: dict[DatasetType, str] = {
        DatasetType.PAYROLL_SUMMARY: "payouts",
        DatasetType.STAFF_ADVANCES: "advances",
    }

    def __init__(self, *, secret_store: SecretStore | None = None) -> None:
        self._secret_store = secret_store or SecretStore()

    async def test_connection(self, credentials: dict[str, Any]) -> dict[str, Any]:
        resolved = await self._resolve_credentials(credentials=credentials)
        payload = await self._request_json(
            resolved,
            endpoint="payouts",
            params={"count": 1},
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
        endpoint = self._DATASET_ENDPOINTS[dataset_type]
        count = int(kwargs.get("count") or 100)
        payload = await self._request_json(
            resolved,
            endpoint=endpoint,
            params={"count": count},
        )
        normalized = _normalize_payload(payload)
        records = self._extract_records(normalized)
        return {
            "dataset_type": dataset_type.value,
            "raw_data": normalized,
            "records": records,
            "line_count": len(records),
            "erp_reported_line_count": len(records),
            "is_resumable": False,
            "next_checkpoint": None,
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
            for key in ("key_id", "key_secret", "base_url"):
                if key in extra and extra[key] is not None:
                    resolved[key] = extra[key]
        resolved.setdefault("base_url", "https://api.razorpay.com/v1/payroll")
        for key in ("key_id", "key_secret"):
            if not resolved.get(key):
                raise ExtractionError(f"Razorpay Payroll credential {key} is required")
        return resolved

    async def _request_json(
        self,
        credentials: dict[str, Any],
        *,
        endpoint: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        url = f"{str(credentials['base_url']).rstrip('/')}/{endpoint.lstrip('/')}"
        auth = (str(credentials["key_id"]), str(credentials["key_secret"]))
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.get(url, auth=auth, params=params, headers={"Accept": "application/json"})
        if response.status_code >= 400:
            raise ExtractionError(f"Razorpay Payroll API error {response.status_code} for {endpoint}")
        payload = response.json()
        if not isinstance(payload, dict):
            raise ExtractionError("Razorpay Payroll API returned non-object payload")
        return payload

    @staticmethod
    def _extract_records(payload: Any) -> list[dict[str, Any]]:
        if not isinstance(payload, dict):
            return []
        for key in ("items", "entities", "records", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        return []
