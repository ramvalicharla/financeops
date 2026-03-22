from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import quote

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


class NetsuiteConnector(AbstractConnector):
    connector_type = ConnectorType.NETSUITE
    connector_version = "4e.1.0"
    supports_resumable_extraction = True
    supported_datasets = set(DatasetType)

    _REST_RECORD_ENDPOINTS: dict[DatasetType, str] = {
        DatasetType.CHART_OF_ACCOUNTS: "/services/rest/record/v1/account",
        DatasetType.VENDOR_MASTER: "/services/rest/record/v1/vendor",
        DatasetType.CUSTOMER_MASTER: "/services/rest/record/v1/customer",
        DatasetType.CURRENCY_MASTER: "/services/rest/record/v1/currency",
    }

    def __init__(self, *, secret_store: SecretStore | None = None) -> None:
        self._secret_store = secret_store or SecretStore()

    async def test_connection(self, credentials: dict[str, Any]) -> dict[str, Any]:
        resolved = await self._resolve_credentials(credentials=credentials)
        payload = await self._request_json(
            resolved,
            method="GET",
            endpoint="/services/rest/record/v1/metadata-catalog",
            params={},
            json_body=None,
        )
        return {
            "ok": True,
            "connector_type": self.connector_type.value,
            "account_id": resolved["account_id"],
            "metadata": payload,
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
        checkpoint = kwargs.get("checkpoint") or {}
        offset = int(checkpoint.get("offset") or kwargs.get("offset") or 0)
        page_size = int(checkpoint.get("page_size") or kwargs.get("page_size") or 1000)

        if dataset_type in self._REST_RECORD_ENDPOINTS:
            endpoint = self._REST_RECORD_ENDPOINTS[dataset_type]
            payload = await self._request_json(
                resolved,
                method="GET",
                endpoint=endpoint,
                params={"offset": offset, "limit": page_size},
                json_body=None,
            )
        else:
            query = self._suiteql_for_dataset(dataset_type, offset=offset, page_size=page_size)
            payload = await self._request_json(
                resolved,
                method="POST",
                endpoint="/services/rest/query/v1/suiteql",
                params={},
                json_body={"q": query},
            )

        normalized = _normalize_payload(payload)
        records = self._extract_records(normalized)
        next_checkpoint = {"offset": offset + page_size, "page_size": page_size} if len(records) >= page_size else None
        result: dict[str, Any] = {
            "dataset_type": dataset_type.value,
            "raw_data": normalized,
            "records": records,
            "line_count": len(records),
            "erp_reported_line_count": len(records),
            "is_resumable": True,
            "next_checkpoint": next_checkpoint,
            "rate_limit_usage": self._extract_rate_limit_info(payload),
        }
        if dataset_type in {DatasetType.TRIAL_BALANCE, DatasetType.BALANCE_SHEET}:
            totals = self._extract_control_totals(normalized)
            if totals:
                result["erp_control_totals"] = totals
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
            for key in (
                "account_id",
                "consumer_key",
                "consumer_secret",
                "token_id",
                "token_secret",
                "base_url",
            ):
                if key in extra and extra[key] is not None:
                    resolved[key] = extra[key]
        if not resolved.get("base_url"):
            account = str(resolved.get("account_id", "")).replace("_", "-")
            resolved["base_url"] = f"https://{account}.suitetalk.api.netsuite.com"
        for key in ("account_id", "consumer_key", "consumer_secret", "token_id", "token_secret"):
            if not resolved.get(key):
                raise ExtractionError(f"NetSuite credential {key} is required")
        return resolved

    def _suiteql_for_dataset(self, dataset_type: DatasetType, *, offset: int, page_size: int) -> str:
        table_hint = {
            DatasetType.GENERAL_LEDGER: "transactionLine",
            DatasetType.TRIAL_BALANCE: "account",
            DatasetType.PROFIT_AND_LOSS: "transactionLine",
            DatasetType.BALANCE_SHEET: "transactionLine",
            DatasetType.INVOICE_REGISTER: "transaction",
            DatasetType.PURCHASE_REGISTER: "transaction",
            DatasetType.BANK_STATEMENT: "transaction",
        }.get(dataset_type, "transaction")
        return (
            f"SELECT * FROM {table_hint} "
            f"ORDER BY id OFFSET {max(offset, 0)} ROWS FETCH NEXT {max(page_size, 1)} ROWS ONLY"
        )

    async def _request_json(
        self,
        credentials: dict[str, Any],
        *,
        method: str,
        endpoint: str,
        params: dict[str, Any],
        json_body: dict[str, Any] | None,
    ) -> dict[str, Any]:
        url = f"{str(credentials['base_url']).rstrip('/')}/{endpoint.lstrip('/')}"
        auth_header = self._oauth1_header(credentials=credentials, method=method, url=url)
        headers = {
            "Authorization": auth_header,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=45.0) as client:
            if method.upper() == "POST":
                response = await client.post(url, headers=headers, params=params, json=json_body or {})
            else:
                response = await client.get(url, headers=headers, params=params)
        if response.status_code >= 400:
            raise ExtractionError(f"NetSuite API error {response.status_code} for {endpoint}")
        payload = response.json()
        if not isinstance(payload, dict):
            raise ExtractionError("NetSuite API returned non-object payload")
        return payload

    def _oauth1_header(self, *, credentials: dict[str, Any], method: str, url: str) -> str:
        nonce = secrets.token_hex(8)
        timestamp = str(int(time.time()))
        signature_method = "HMAC-SHA256"
        oauth_params = {
            "oauth_consumer_key": str(credentials["consumer_key"]),
            "oauth_token": str(credentials["token_id"]),
            "oauth_signature_method": signature_method,
            "oauth_timestamp": timestamp,
            "oauth_nonce": nonce,
            "oauth_version": "1.0",
        }
        # Minimal deterministic signature for request validation in tests.
        param_base = "&".join(f"{quote(k, safe='')}={quote(v, safe='')}" for k, v in sorted(oauth_params.items()))
        base_string = f"{method.upper()}&{quote(url, safe='')}&{quote(param_base, safe='')}"
        key = (
            f"{quote(str(credentials['consumer_secret']), safe='')}&"
            f"{quote(str(credentials['token_secret']), safe='')}"
        )
        signature = base64.b64encode(hmac.new(key.encode(), base_string.encode(), hashlib.sha256).digest()).decode()
        oauth_params["oauth_signature"] = signature
        header_values = ", ".join(f'{k}="{quote(v, safe="~")}"' for k, v in sorted(oauth_params.items()))
        return f"OAuth realm=\"{credentials['account_id']}\", {header_values}"

    @staticmethod
    def _extract_records(payload: Any) -> list[dict[str, Any]]:
        if not isinstance(payload, dict):
            return []
        for key in ("items", "records", "results", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
            if isinstance(value, dict):
                for nested_key in ("items", "records"):
                    nested = value.get(nested_key)
                    if isinstance(nested, list):
                        return [item for item in nested if isinstance(item, dict)]
        return []

    @staticmethod
    def _extract_control_totals(payload: Any) -> dict[str, Decimal]:
        totals: dict[str, Decimal] = {}
        if isinstance(payload, dict):
            for key, value in payload.items():
                if isinstance(value, Decimal) and any(
                    token in key.lower() for token in ("total", "balance", "debit", "credit")
                ):
                    totals[key] = value
                elif isinstance(value, dict):
                    totals.update(NetsuiteConnector._extract_control_totals(value))
        return totals

    @staticmethod
    def _extract_rate_limit_info(payload: Any) -> dict[str, Any]:
        if isinstance(payload, dict):
            usage = payload.get("rateLimit")
            if isinstance(usage, dict):
                return usage
        return {}
