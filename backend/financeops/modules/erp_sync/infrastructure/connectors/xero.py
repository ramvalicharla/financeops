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


class XeroConnector(AbstractConnector):
    connector_type = ConnectorType.XERO
    connector_version = "4e.1.0"
    supports_resumable_extraction = True
    supported_datasets = {
        DatasetType.TRIAL_BALANCE,
        DatasetType.GENERAL_LEDGER,
        DatasetType.PROFIT_AND_LOSS,
        DatasetType.BALANCE_SHEET,
        DatasetType.ACCOUNTS_RECEIVABLE,
        DatasetType.ACCOUNTS_PAYABLE,
        DatasetType.INVOICE_REGISTER,
        DatasetType.PURCHASE_REGISTER,
        DatasetType.BANK_STATEMENT,
        DatasetType.CHART_OF_ACCOUNTS,
        DatasetType.VENDOR_MASTER,
        DatasetType.CUSTOMER_MASTER,
    }

    _DATASET_ENDPOINTS: dict[DatasetType, str] = {
        DatasetType.TRIAL_BALANCE: "Reports/TrialBalance",
        DatasetType.GENERAL_LEDGER: "Reports/GeneralLedger",
        DatasetType.PROFIT_AND_LOSS: "Reports/ProfitAndLoss",
        DatasetType.BALANCE_SHEET: "Reports/BalanceSheet",
        DatasetType.ACCOUNTS_RECEIVABLE: "Reports/AgedReceivablesByContact",
        DatasetType.ACCOUNTS_PAYABLE: "Reports/AgedPayablesByContact",
        DatasetType.INVOICE_REGISTER: "Invoices",
        DatasetType.PURCHASE_REGISTER: "Receipts",
        DatasetType.BANK_STATEMENT: "BankTransactions",
        DatasetType.CHART_OF_ACCOUNTS: "Accounts",
        DatasetType.VENDOR_MASTER: "Contacts",
        DatasetType.CUSTOMER_MASTER: "Contacts",
    }

    def __init__(self, *, secret_store: SecretStore | None = None) -> None:
        self._secret_store = secret_store or SecretStore()

    async def test_connection(self, credentials: dict[str, Any]) -> dict[str, Any]:
        resolved = await self._resolve_credentials(credentials=credentials)
        access_token = await self._resolve_access_token(resolved)
        payload = await self._request_json(
            resolved,
            endpoint="Organisation",
            access_token=access_token,
            params={},
        )
        return {
            "ok": True,
            "connector_type": self.connector_type.value,
            "tenant_id": resolved["tenant_id"],
            "organisation": payload,
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
        access_token = await self._resolve_access_token(resolved)
        checkpoint = kwargs.get("checkpoint") or {}
        page = int(checkpoint.get("page") or kwargs.get("page") or 1)
        page_size = int(checkpoint.get("page_size") or kwargs.get("page_size") or 100)
        endpoint = self._DATASET_ENDPOINTS[dataset_type]
        params: dict[str, Any] = {"page": page}
        if dataset_type in {
            DatasetType.INVOICE_REGISTER,
            DatasetType.PURCHASE_REGISTER,
            DatasetType.BANK_STATEMENT,
            DatasetType.VENDOR_MASTER,
            DatasetType.CUSTOMER_MASTER,
        }:
            params["pageSize"] = page_size

        payload = await self._request_json(
            resolved,
            endpoint=endpoint,
            access_token=access_token,
            params=params,
        )
        normalized = _normalize_payload(payload)
        records = self._extract_records(dataset_type=dataset_type, payload=normalized)
        next_checkpoint = {"page": page + 1, "page_size": page_size} if len(records) >= page_size else None
        result: dict[str, Any] = {
            "dataset_type": dataset_type.value,
            "raw_data": normalized,
            "records": records,
            "line_count": len(records),
            "erp_reported_line_count": len(records),
            "is_resumable": True,
            "next_checkpoint": next_checkpoint,
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
                "client_id",
                "client_secret",
                "refresh_token",
                "tenant_id",
                "access_token",
                "base_url",
            ):
                if key in extra and extra[key] is not None:
                    resolved[key] = extra[key]
        resolved.setdefault("base_url", "https://api.xero.com/api.xro/2.0")
        for key in ("client_id", "client_secret", "tenant_id"):
            if not resolved.get(key):
                raise ExtractionError(f"Xero credential {key} is required")
        return resolved

    async def _resolve_access_token(self, credentials: dict[str, Any]) -> str:
        access_token = credentials.get("access_token")
        if access_token:
            return str(access_token)
        refresh_token = credentials.get("refresh_token")
        if not refresh_token:
            raise ExtractionError("Xero refresh_token or access_token is required")
        data = {"grant_type": "refresh_token", "refresh_token": str(refresh_token)}
        auth = (str(credentials["client_id"]), str(credentials["client_secret"]))
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(
                "https://identity.xero.com/connect/token",
                data=data,
                auth=auth,
                headers={"Accept": "application/json"},
            )
        if response.status_code >= 400:
            raise ExtractionError(f"Xero token refresh failed ({response.status_code})")
        payload = response.json()
        token = payload.get("access_token")
        if not token:
            raise ExtractionError("Xero token refresh response missing access_token")
        return str(token)

    async def _request_json(
        self,
        credentials: dict[str, Any],
        *,
        endpoint: str,
        access_token: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        url = f"{str(credentials['base_url']).rstrip('/')}/{endpoint.lstrip('/')}"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Xero-Tenant-Id": str(credentials["tenant_id"]),
            "Accept": "application/json",
        }
        max_attempts = 4
        async with httpx.AsyncClient(timeout=45.0) as client:
            for attempt in range(max_attempts):
                response = await client.get(url, headers=headers, params=params)
                if response.status_code != 429:
                    break
                if attempt == max_attempts - 1:
                    break
                await asyncio.sleep(2**attempt)
        if response.status_code >= 400:
            raise ExtractionError(f"Xero API error {response.status_code} for {endpoint}")
        payload = response.json()
        if not isinstance(payload, dict):
            raise ExtractionError("Xero API returned non-object payload")
        return payload

    @staticmethod
    def _extract_records(*, dataset_type: DatasetType, payload: Any) -> list[dict[str, Any]]:
        if not isinstance(payload, dict):
            return []
        if dataset_type in {
            DatasetType.TRIAL_BALANCE,
            DatasetType.GENERAL_LEDGER,
            DatasetType.PROFIT_AND_LOSS,
            DatasetType.BALANCE_SHEET,
            DatasetType.ACCOUNTS_RECEIVABLE,
            DatasetType.ACCOUNTS_PAYABLE,
        }:
            reports = payload.get("Reports")
            if isinstance(reports, list) and reports:
                flattened: list[dict[str, Any]] = []
                for report in reports:
                    if isinstance(report, dict):
                        rows = report.get("Rows")
                        if isinstance(rows, list):
                            flattened.extend([item for item in rows if isinstance(item, dict)])
                        else:
                            flattened.append(report)
                return flattened
        for key in ("Invoices", "BankTransactions", "Accounts", "Contacts", "records", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                items = [item for item in value if isinstance(item, dict)]
                if dataset_type == DatasetType.VENDOR_MASTER:
                    return [row for row in items if str(row.get("IsSupplier", "")).lower() in {"true", "1"}]
                if dataset_type == DatasetType.CUSTOMER_MASTER:
                    return [row for row in items if str(row.get("IsCustomer", "")).lower() in {"true", "1"}]
                return items
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
                    nested = XeroConnector._extract_control_totals(value)
                    totals.update(nested)
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict):
                            totals.update(XeroConnector._extract_control_totals(item))
        return totals
