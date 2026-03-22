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


class Dynamics365Connector(AbstractConnector):
    connector_type = ConnectorType.DYNAMICS_365
    connector_version = "4e.1.0"
    supports_resumable_extraction = True
    supported_datasets = {
        DatasetType.TRIAL_BALANCE,
        DatasetType.GENERAL_LEDGER,
        DatasetType.PROFIT_AND_LOSS,
        DatasetType.BALANCE_SHEET,
        DatasetType.ACCOUNTS_RECEIVABLE,
        DatasetType.ACCOUNTS_PAYABLE,
        DatasetType.AR_AGEING,
        DatasetType.AP_AGEING,
        DatasetType.INVOICE_REGISTER,
        DatasetType.PURCHASE_REGISTER,
        DatasetType.BANK_STATEMENT,
        DatasetType.FIXED_ASSET_REGISTER,
        DatasetType.CHART_OF_ACCOUNTS,
        DatasetType.VENDOR_MASTER,
        DatasetType.CUSTOMER_MASTER,
    }

    _DATASET_ENTITY_MAP: dict[DatasetType, str] = {
        DatasetType.TRIAL_BALANCE: "trialBalances",
        DatasetType.GENERAL_LEDGER: "generalLedgerEntries",
        DatasetType.PROFIT_AND_LOSS: "profitAndLoss",
        DatasetType.BALANCE_SHEET: "balanceSheet",
        DatasetType.ACCOUNTS_RECEIVABLE: "customerLedgerEntries",
        DatasetType.ACCOUNTS_PAYABLE: "vendorLedgerEntries",
        DatasetType.AR_AGEING: "agedAccountsReceivable",
        DatasetType.AP_AGEING: "agedAccountsPayable",
        DatasetType.INVOICE_REGISTER: "salesInvoices",
        DatasetType.PURCHASE_REGISTER: "purchaseInvoices",
        DatasetType.BANK_STATEMENT: "bankAccountLedgerEntries",
        DatasetType.FIXED_ASSET_REGISTER: "fixedAssets",
        DatasetType.CHART_OF_ACCOUNTS: "accounts",
        DatasetType.VENDOR_MASTER: "vendors",
        DatasetType.CUSTOMER_MASTER: "customers",
    }

    def __init__(self, *, secret_store: SecretStore | None = None) -> None:
        self._secret_store = secret_store or SecretStore()

    async def test_connection(self, credentials: dict[str, Any]) -> dict[str, Any]:
        resolved = await self._resolve_credentials(credentials=credentials)
        token = await self._resolve_access_token(resolved)
        endpoint = self._build_endpoint(resolved, "companies")
        payload = await self._request_json(endpoint=endpoint, access_token=token, params={"$top": 1, "$skip": 0})
        return {
            "ok": True,
            "connector_type": self.connector_type.value,
            "dynamics_product": self._resolve_product(resolved),
            "payload": payload,
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
        skip = int(checkpoint.get("skip") or kwargs.get("skip") or 0)
        page_size = int(checkpoint.get("page_size") or kwargs.get("page_size") or 1000)
        endpoint = self._build_endpoint(resolved, self._DATASET_ENTITY_MAP[dataset_type])
        payload = await self._request_json(
            endpoint=endpoint,
            access_token=token,
            params={"$top": page_size, "$skip": skip},
        )
        normalized = _normalize_payload(payload)
        records = self._extract_records(normalized)
        next_checkpoint = {"skip": skip + page_size, "page_size": page_size} if len(records) >= page_size else None
        result: dict[str, Any] = {
            "dataset_type": dataset_type.value,
            "raw_data": normalized,
            "records": records,
            "line_count": len(records),
            "erp_reported_line_count": len(records),
            "is_resumable": True,
            "next_checkpoint": next_checkpoint,
            "dynamics_product": self._resolve_product(resolved),
        }
        if dataset_type in {DatasetType.TRIAL_BALANCE, DatasetType.BALANCE_SHEET}:
            totals = self._extract_control_totals(records)
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
                "tenant_id",
                "client_id",
                "client_secret",
                "environment_url",
                "dynamics_product",
                "access_token",
                "scope",
            ):
                if key in extra and extra[key] is not None:
                    resolved[key] = extra[key]
        for key in ("tenant_id", "client_id", "client_secret", "environment_url"):
            if not resolved.get(key):
                raise ExtractionError(f"Dynamics 365 credential {key} is required")
        return resolved

    @staticmethod
    def _resolve_product(credentials: dict[str, Any]) -> str:
        product = str(credentials.get("dynamics_product", "BUSINESS_CENTRAL")).strip().upper()
        if product == "FINANCE_OPERATIONS":
            return "FINANCE_OPERATIONS"
        return "BUSINESS_CENTRAL"

    async def _resolve_access_token(self, credentials: dict[str, Any]) -> str:
        access_token = credentials.get("access_token")
        if access_token:
            return str(access_token)
        tenant_id = str(credentials["tenant_id"])
        token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
        scope = str(credentials.get("scope") or f"{str(credentials['environment_url']).rstrip('/')}/.default")
        data = {
            "client_id": str(credentials["client_id"]),
            "client_secret": str(credentials["client_secret"]),
            "grant_type": "client_credentials",
            "scope": scope,
        }
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(token_url, data=data, headers={"Accept": "application/json"})
        if response.status_code >= 400:
            raise ExtractionError(f"Dynamics 365 token request failed ({response.status_code})")
        payload = response.json()
        token = payload.get("access_token")
        if not token:
            raise ExtractionError("Dynamics 365 token response missing access_token")
        return str(token)

    def _build_endpoint(self, credentials: dict[str, Any], entity: str) -> str:
        base_url = str(credentials["environment_url"]).rstrip("/")
        product = self._resolve_product(credentials)
        if product == "FINANCE_OPERATIONS":
            return f"{base_url}/data/{entity}"
        return f"{base_url}/api/v2.0/{entity}"

    async def _request_json(self, *, endpoint: str, access_token: str, params: dict[str, Any]) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.get(endpoint, headers=headers, params=params)
        if response.status_code >= 400:
            raise ExtractionError(f"Dynamics 365 API error {response.status_code} for {endpoint}")
        payload = response.json()
        if not isinstance(payload, dict):
            raise ExtractionError("Dynamics 365 API returned non-object payload")
        return payload

    @staticmethod
    def _extract_records(payload: Any) -> list[dict[str, Any]]:
        if not isinstance(payload, dict):
            return []
        value = payload.get("value")
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        for key in ("records", "items", "data"):
            nested = payload.get(key)
            if isinstance(nested, list):
                return [item for item in nested if isinstance(item, dict)]
        return []

    @staticmethod
    def _extract_control_totals(records: list[dict[str, Any]]) -> dict[str, Decimal]:
        totals: dict[str, Decimal] = {}
        for row in records:
            for key, value in row.items():
                if isinstance(value, Decimal) and any(
                    token in key.lower() for token in ("total", "balance", "debit", "credit")
                ):
                    totals[key] = totals.get(key, Decimal("0")) + value
        return totals
