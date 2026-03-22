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
    if isinstance(value, (int, float)):
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return value
    return value


def _normalize_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _normalize_payload(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_normalize_payload(item) for item in value]
    return _to_decimal_if_numeric(value)


class PlaidConnector(AbstractConnector):
    connector_type = ConnectorType.PLAID
    connector_version = "4e.1.0"
    supports_resumable_extraction = True
    supported_datasets = {
        DatasetType.BANK_STATEMENT,
        DatasetType.BANK_TRANSACTION_REGISTER,
    }

    def __init__(self, *, secret_store: SecretStore | None = None) -> None:
        self._secret_store = secret_store or SecretStore()

    async def test_connection(self, credentials: dict[str, Any]) -> dict[str, Any]:
        resolved = await self._resolve_credentials(credentials=credentials)
        payload = await self._request_json(
            resolved,
            endpoint="/item/get",
            body={"access_token": resolved["access_token"]},
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
        cursor = checkpoint.get("cursor") or kwargs.get("cursor")
        sync_payload = await self._request_json(
            resolved,
            endpoint="/transactions/sync",
            body={
                "access_token": resolved["access_token"],
                "cursor": cursor,
                "count": int(kwargs.get("count") or 100),
            },
        )
        normalized = _normalize_payload(sync_payload)
        records = self._extract_records(normalized)
        next_cursor = sync_payload.get("next_cursor") if isinstance(sync_payload, dict) else None
        result: dict[str, Any] = {
            "dataset_type": dataset_type.value,
            "raw_data": normalized,
            "records": records,
            "line_count": len(records),
            "erp_reported_line_count": len(records),
            "is_resumable": True,
            "next_checkpoint": {"cursor": next_cursor} if next_cursor else None,
        }
        if dataset_type == DatasetType.BANK_STATEMENT:
            balance_payload = await self._request_json(
                resolved,
                endpoint="/accounts/balance/get",
                body={"access_token": resolved["access_token"]},
            )
            result["erp_control_totals"] = self._extract_balance_totals(_normalize_payload(balance_payload))
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
            for key in ("client_id", "secret", "access_token", "environment", "base_url"):
                if key in extra and extra[key] is not None:
                    resolved[key] = extra[key]
        env = str(resolved.get("environment") or "sandbox").lower()
        default_base = {
            "sandbox": "https://sandbox.plaid.com",
            "development": "https://development.plaid.com",
            "production": "https://production.plaid.com",
        }.get(env, "https://sandbox.plaid.com")
        resolved.setdefault("base_url", default_base)
        for key in ("client_id", "secret", "access_token"):
            if not resolved.get(key):
                raise ExtractionError(f"Plaid credential {key} is required")
        return resolved

    async def _request_json(self, credentials: dict[str, Any], *, endpoint: str, body: dict[str, Any]) -> dict[str, Any]:
        url = f"{str(credentials['base_url']).rstrip('/')}/{endpoint.lstrip('/')}"
        payload = {"client_id": credentials["client_id"], "secret": credentials["secret"], **body}
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(url, json=payload, headers={"Accept": "application/json"})
        if response.status_code >= 400:
            raise ExtractionError(f"Plaid API error {response.status_code} for {endpoint}")
        result = response.json()
        if not isinstance(result, dict):
            raise ExtractionError("Plaid API returned non-object payload")
        return result

    @staticmethod
    def _extract_records(payload: Any) -> list[dict[str, Any]]:
        if not isinstance(payload, dict):
            return []
        records: list[dict[str, Any]] = []
        for key in ("added", "modified", "removed", "transactions"):
            value = payload.get(key)
            if isinstance(value, list):
                records.extend([row for row in value if isinstance(row, dict)])
        return records

    @staticmethod
    def _extract_balance_totals(payload: Any) -> dict[str, Decimal]:
        if not isinstance(payload, dict):
            return {}
        accounts = payload.get("accounts")
        total = Decimal("0")
        if isinstance(accounts, list):
            for account in accounts:
                if not isinstance(account, dict):
                    continue
                balances = account.get("balances")
                if not isinstance(balances, dict):
                    continue
                current = balances.get("current")
                if isinstance(current, Decimal):
                    total += current
        return {"total_account_balance": total}
