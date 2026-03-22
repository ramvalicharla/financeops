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


def _normalize_amount_fields(value: Any, *, parent_key: str | None = None) -> Any:
    if isinstance(value, dict):
        normalized: dict[str, Any] = {}
        for key, item in value.items():
            normalized[key] = _normalize_amount_fields(item, parent_key=key.lower())
        return normalized
    if isinstance(value, list):
        return [_normalize_amount_fields(item, parent_key=parent_key) for item in value]
    if parent_key and "amount" in parent_key:
        amount = _to_decimal(value)
        if amount is not None:
            return (amount / Decimal("100")).quantize(Decimal("0.01"))
    return value


class RazorpayConnector(AbstractConnector):
    connector_type = ConnectorType.RAZORPAY
    connector_version = "4e.1.0"
    supports_resumable_extraction = True
    supported_datasets = {
        DatasetType.BANK_STATEMENT,
        DatasetType.BANK_TRANSACTION_REGISTER,
        DatasetType.INVOICE_REGISTER,
        DatasetType.ACCOUNTS_RECEIVABLE,
    }

    _DATASET_ENDPOINTS: dict[DatasetType, str] = {
        DatasetType.BANK_STATEMENT: "settlements",
        DatasetType.BANK_TRANSACTION_REGISTER: "payments",
        DatasetType.INVOICE_REGISTER: "invoices",
        DatasetType.ACCOUNTS_RECEIVABLE: "payment_links",
    }

    def __init__(self, *, secret_store: SecretStore | None = None) -> None:
        self._secret_store = secret_store or SecretStore()

    async def test_connection(self, credentials: dict[str, Any]) -> dict[str, Any]:
        resolved = await self._resolve_credentials(credentials=credentials)
        payload = await self._request_json(
            resolved,
            endpoint="payments",
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
        checkpoint = kwargs.get("checkpoint") or {}
        from_timestamp = int(checkpoint.get("from_timestamp") or kwargs.get("from_timestamp") or 0)
        count = int(checkpoint.get("count") or kwargs.get("count") or 100)
        last_id = checkpoint.get("last_id") or kwargs.get("last_id")
        params: dict[str, Any] = {"from": from_timestamp, "count": count}
        if last_id:
            params["skip"] = 1

        endpoint = self._DATASET_ENDPOINTS[dataset_type]
        payload = await self._request_json(resolved, endpoint=endpoint, params=params)
        normalized = _normalize_amount_fields(payload)
        records = self._extract_records(normalized)
        next_checkpoint = None
        if records:
            latest_created = max(
                int(r.get("created_at", 0)) for r in records if isinstance(r, dict) and str(r.get("created_at", "")).isdigit()
            ) if any(str(r.get("created_at", "")).isdigit() for r in records if isinstance(r, dict)) else from_timestamp
            last_row = records[-1] if records else {}
            next_checkpoint = {
                "from_timestamp": latest_created,
                "last_id": str(last_row.get("id", "")),
                "count": count,
            }
            if len(records) < count:
                next_checkpoint = None
        result: dict[str, Any] = {
            "dataset_type": dataset_type.value,
            "raw_data": normalized,
            "records": records,
            "line_count": len(records),
            "erp_reported_line_count": len(records),
            "is_resumable": True,
            "next_checkpoint": next_checkpoint,
        }
        if dataset_type == DatasetType.BANK_STATEMENT:
            result["erp_control_totals"] = self._compute_settled_totals(records)
        return result

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
        resolved.setdefault("base_url", "https://api.razorpay.com/v1")
        for key in ("key_id", "key_secret"):
            if not resolved.get(key):
                raise ExtractionError(f"Razorpay credential {key} is required")
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
            raise ExtractionError(f"Razorpay API error {response.status_code} for {endpoint}")
        payload = response.json()
        if not isinstance(payload, dict):
            raise ExtractionError("Razorpay API returned non-object payload")
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

    @staticmethod
    def _compute_settled_totals(records: list[dict[str, Any]]) -> dict[str, Decimal]:
        total = Decimal("0")
        for row in records:
            amount = row.get("amount")
            if isinstance(amount, Decimal):
                total += amount
        return {"total_settled_amount": total}
