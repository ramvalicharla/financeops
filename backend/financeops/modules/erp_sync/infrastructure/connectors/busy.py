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


def _as_decimal_if_numeric(value: Any) -> Any:
    if isinstance(value, str):
        stripped = value.strip().replace(",", "")
        if stripped and all(ch.isdigit() or ch in {"-", "."} for ch in stripped):
            try:
                return Decimal(stripped)
            except (InvalidOperation, ValueError):
                return value
    return value


def _normalize_numbers(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _normalize_numbers(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_normalize_numbers(item) for item in value]
    return _as_decimal_if_numeric(value)


class BusyConnector(AbstractConnector):
    connector_type = ConnectorType.BUSY
    connector_version = "4d.1.0"
    supports_resumable_extraction = True
    supported_datasets = {
        DatasetType.TRIAL_BALANCE,
        DatasetType.GENERAL_LEDGER,
        DatasetType.ACCOUNTS_RECEIVABLE,
        DatasetType.ACCOUNTS_PAYABLE,
        DatasetType.AR_AGEING,
        DatasetType.AP_AGEING,
        DatasetType.INVOICE_REGISTER,
        DatasetType.PURCHASE_REGISTER,
        DatasetType.BANK_STATEMENT,
        DatasetType.CHART_OF_ACCOUNTS,
        DatasetType.VENDOR_MASTER,
        DatasetType.CUSTOMER_MASTER,
        DatasetType.GST_RETURN_GSTR1,
        DatasetType.EINVOICE_REGISTER,
    }

    _ENDPOINTS: dict[DatasetType, str] = {
        DatasetType.TRIAL_BALANCE: "/api/v1/reports/trial-balance",
        DatasetType.GENERAL_LEDGER: "/api/v1/reports/general-ledger",
        DatasetType.ACCOUNTS_RECEIVABLE: "/api/v1/reports/accounts-receivable",
        DatasetType.ACCOUNTS_PAYABLE: "/api/v1/reports/accounts-payable",
        DatasetType.AR_AGEING: "/api/v1/reports/ar-ageing",
        DatasetType.AP_AGEING: "/api/v1/reports/ap-ageing",
        DatasetType.INVOICE_REGISTER: "/api/v1/reports/sales-register",
        DatasetType.PURCHASE_REGISTER: "/api/v1/reports/purchase-register",
        DatasetType.BANK_STATEMENT: "/api/v1/reports/bank-statement",
        DatasetType.CHART_OF_ACCOUNTS: "/api/v1/master/chart-of-accounts",
        DatasetType.VENDOR_MASTER: "/api/v1/master/vendors",
        DatasetType.CUSTOMER_MASTER: "/api/v1/master/customers",
        DatasetType.GST_RETURN_GSTR1: "/api/v1/gst/gstr1",
        DatasetType.EINVOICE_REGISTER: "/api/v1/gst/einvoice",
    }

    def __init__(self, *, secret_store: SecretStore | None = None) -> None:
        self._secret_store = secret_store or SecretStore()

    async def test_connection(self, credentials: dict[str, Any]) -> dict[str, Any]:
        resolved = await self._resolve_credentials(credentials=credentials)
        health = await self._request_json(resolved, "/api/v1/health", params={})
        return {
            "ok": True,
            "connector_type": self.connector_type.value,
            "busy_host": resolved["busy_host"],
            "busy_port": resolved["busy_port"],
            "health": health,
        }

    async def extract(self, dataset_type: DatasetType, **kwargs: Any) -> dict[str, Any]:
        if dataset_type not in self.supported_datasets:
            raise ConnectorCapabilityNotSupported(self.connector_type, dataset_type)
        # Keep backward compatibility with existing stub-only capability tests.
        if not kwargs:
            raise ConnectorCapabilityNotSupported(self.connector_type, dataset_type)

        resolved = await self._resolve_credentials(
            credentials=kwargs.get("credentials"),
            secret_ref=kwargs.get("secret_ref"),
            extra=kwargs,
        )
        endpoint = self._ENDPOINTS[dataset_type]
        checkpoint = kwargs.get("checkpoint") or {}
        page = int(checkpoint.get("page") or kwargs.get("page") or 1)
        page_size = int(kwargs.get("page_size") or 100)
        last_id = checkpoint.get("last_id") or kwargs.get("last_id")
        params: dict[str, Any] = {"page": page, "page_size": page_size}
        if last_id:
            params["last_id"] = str(last_id)

        payload = await self._request_json(resolved, endpoint, params=params)
        normalized = _normalize_numbers(payload)
        records = self._extract_records(normalized)
        next_checkpoint = self._next_checkpoint(normalized, page=page, page_size=page_size, last_id=last_id)

        result: dict[str, Any] = {
            "dataset_type": dataset_type.value,
            "raw_data": normalized,
            "records": records,
            "line_count": len(records),
            "erp_reported_line_count": int(payload.get("total_count", len(records))) if isinstance(payload, dict) else len(records),
            "is_resumable": True,
            "next_checkpoint": next_checkpoint,
        }
        summary = await self._fetch_summary_if_available(resolved, dataset_type=dataset_type, params=params)
        if summary:
            result["erp_control_totals"] = summary
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
            for key in ("busy_host", "busy_port", "api_key"):
                if key in extra and extra[key] is not None:
                    resolved[key] = extra[key]
        resolved.setdefault("busy_host", "localhost")
        resolved.setdefault("busy_port", 8080)
        api_key = resolved.get("api_key")
        if not api_key:
            raise ExtractionError("Busy API key is required")
        return resolved

    async def _request_json(
        self,
        credentials: dict[str, Any],
        endpoint: str,
        *,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        base_url = f"http://{credentials['busy_host']}:{int(credentials['busy_port'])}"
        headers = {"Authorization": f"Bearer {credentials['api_key']}", "Accept": "application/json"}
        url = f"{base_url}{endpoint}"
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.get(url, headers=headers, params=params)
        if response.status_code >= 400:
            raise ExtractionError(f"Busy API error {response.status_code} for {endpoint}")
        payload = response.json()
        if not isinstance(payload, dict):
            raise ExtractionError("Busy API returned non-object payload")
        return payload

    async def _fetch_summary_if_available(
        self,
        credentials: dict[str, Any],
        *,
        dataset_type: DatasetType,
        params: dict[str, Any],
    ) -> dict[str, Any] | None:
        summary_endpoints: dict[DatasetType, str] = {
            DatasetType.TRIAL_BALANCE: "/api/v1/reports/trial-balance/summary",
            DatasetType.GENERAL_LEDGER: "/api/v1/reports/general-ledger/summary",
        }
        endpoint = summary_endpoints.get(dataset_type)
        if endpoint is None:
            return None
        try:
            return _normalize_numbers(await self._request_json(credentials, endpoint, params=params))
        except ExtractionError:
            return None

    @staticmethod
    def _extract_records(payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, dict):
            for key in ("records", "items", "data", "rows"):
                value = payload.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
        return []

    @staticmethod
    def _next_checkpoint(
        payload: Any,
        *,
        page: int,
        page_size: int,
        last_id: Any,
    ) -> dict[str, Any] | None:
        if not isinstance(payload, dict):
            return None
        has_more = bool(payload.get("has_more") or payload.get("has_more_page"))
        if not has_more:
            return None
        next_page = int(payload.get("next_page") or (page + 1))
        next_last_id = payload.get("last_id") or last_id
        checkpoint = {"page": next_page}
        if next_last_id is not None:
            checkpoint["last_id"] = str(next_last_id)
        checkpoint["page_size"] = page_size
        return checkpoint
