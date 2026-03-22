from __future__ import annotations

import asyncio
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


class FreshbooksConnector(AbstractConnector):
    connector_type = ConnectorType.FRESHBOOKS
    connector_version = "4e.1.0"
    supports_resumable_extraction = True
    supported_datasets = {
        DatasetType.INVOICE_REGISTER,
        DatasetType.ACCOUNTS_RECEIVABLE,
        DatasetType.EXPENSE_CLAIMS,
        DatasetType.CHART_OF_ACCOUNTS,
        DatasetType.CUSTOMER_MASTER,
    }

    _DATASET_ENDPOINTS: dict[DatasetType, str] = {
        DatasetType.INVOICE_REGISTER: "accounting/account/{account_id}/invoices/invoices",
        DatasetType.ACCOUNTS_RECEIVABLE: "accounting/account/{account_id}/reports/accounting/ar_aging",
        DatasetType.EXPENSE_CLAIMS: "accounting/account/{account_id}/expenses/expenses",
        DatasetType.CHART_OF_ACCOUNTS: "accounting/account/{account_id}/accounts/accounts",
        DatasetType.CUSTOMER_MASTER: "accounting/account/{account_id}/users/clients",
    }

    def __init__(self, *, secret_store: SecretStore | None = None) -> None:
        self._secret_store = secret_store or SecretStore()

    async def test_connection(self, credentials: dict[str, Any]) -> dict[str, Any]:
        resolved = await self._resolve_credentials(credentials=credentials)
        token = await self._resolve_access_token(resolved)
        payload = await self._request_json(
            resolved,
            access_token=token,
            endpoint=f"auth/api/v1/users/me",
            params={},
        )
        return {
            "ok": True,
            "connector_type": self.connector_type.value,
            "account_id": resolved["account_id"],
            "user": payload,
        }

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
        token = await self._resolve_access_token(resolved)
        checkpoint = kwargs.get("checkpoint") or {}
        page = int(checkpoint.get("page") or kwargs.get("page") or 1)
        page_size = int(checkpoint.get("page_size") or kwargs.get("page_size") or 100)
        endpoint = self._DATASET_ENDPOINTS[dataset_type].format(account_id=resolved["account_id"])

        params = {"page": page, "per_page": page_size}
        payload = await self._request_json(
            resolved,
            access_token=token,
            endpoint=endpoint,
            params=params,
        )
        normalized = _normalize_payload(payload)
        records = self._extract_records(dataset_type=dataset_type, payload=normalized)
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
            for key in (
                "client_id",
                "client_secret",
                "refresh_token",
                "account_id",
                "access_token",
                "base_url",
            ):
                if key in extra and extra[key] is not None:
                    resolved[key] = extra[key]
        resolved.setdefault("base_url", "https://api.freshbooks.com")
        for key in ("client_id", "client_secret", "account_id"):
            if not resolved.get(key):
                raise ExtractionError(f"FreshBooks credential {key} is required")
        return resolved

    async def _resolve_access_token(self, credentials: dict[str, Any]) -> str:
        access_token = credentials.get("access_token")
        if access_token:
            return str(access_token)
        refresh_token = credentials.get("refresh_token")
        if not refresh_token:
            raise ExtractionError("FreshBooks refresh_token or access_token is required")

        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(
                "https://api.freshbooks.com/auth/oauth/token",
                json={
                    "grant_type": "refresh_token",
                    "refresh_token": str(refresh_token),
                    "client_id": str(credentials["client_id"]),
                    "client_secret": str(credentials["client_secret"]),
                },
                headers={"Accept": "application/json"},
            )
        if response.status_code >= 400:
            raise ExtractionError(f"FreshBooks token refresh failed ({response.status_code})")
        payload = response.json()
        token = payload.get("access_token")
        if not token:
            raise ExtractionError("FreshBooks token response missing access_token")
        return str(token)

    async def _request_json(
        self,
        credentials: dict[str, Any],
        *,
        access_token: str,
        endpoint: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        url = f"{str(credentials['base_url']).rstrip('/')}/{endpoint.lstrip('/')}"
        headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
        max_attempts = 4
        async with httpx.AsyncClient(timeout=45.0) as client:
            for attempt in range(max_attempts):
                response = await client.get(url, headers=headers, params=params)
                if response.status_code != 429:
                    break
                if attempt == max_attempts - 1:
                    break
                reset_header = response.headers.get("X-RateLimit-Reset")
                if reset_header and reset_header.isdigit():
                    wait_seconds = max(1, int(reset_header))
                else:
                    wait_seconds = 2**attempt
                await asyncio.sleep(wait_seconds)
        if response.status_code >= 400:
            raise ExtractionError(f"FreshBooks API error {response.status_code} for {endpoint}")
        payload = response.json()
        if not isinstance(payload, dict):
            raise ExtractionError("FreshBooks API returned non-object payload")
        return payload

    @staticmethod
    def _extract_records(*, dataset_type: DatasetType, payload: Any) -> list[dict[str, Any]]:
        if not isinstance(payload, dict):
            return []
        dataset_keys: dict[DatasetType, tuple[str, ...]] = {
            DatasetType.INVOICE_REGISTER: ("invoices", "invoice", "items", "data"),
            DatasetType.ACCOUNTS_RECEIVABLE: ("rows", "entries", "items", "data"),
            DatasetType.EXPENSE_CLAIMS: ("expenses", "items", "data"),
            DatasetType.CHART_OF_ACCOUNTS: ("accounts", "items", "data"),
            DatasetType.CUSTOMER_MASTER: ("clients", "items", "data"),
        }
        for key in dataset_keys.get(dataset_type, ("items", "data")):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
            if isinstance(value, dict):
                for nested_key in ("items", "data", key):
                    nested = value.get(nested_key)
                    if isinstance(nested, list):
                        return [item for item in nested if isinstance(item, dict)]
        return []
