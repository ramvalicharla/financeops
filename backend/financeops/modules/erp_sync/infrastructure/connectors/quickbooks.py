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


class QuickbooksConnector(AbstractConnector):
    connector_type = ConnectorType.QUICKBOOKS
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
        DatasetType.CHART_OF_ACCOUNTS,
        DatasetType.VENDOR_MASTER,
        DatasetType.CUSTOMER_MASTER,
    }

    _DATASET_ENDPOINTS: dict[DatasetType, str] = {
        DatasetType.TRIAL_BALANCE: "reports/TrialBalance",
        DatasetType.GENERAL_LEDGER: "reports/GeneralLedger",
        DatasetType.PROFIT_AND_LOSS: "reports/ProfitAndLoss",
        DatasetType.BALANCE_SHEET: "reports/BalanceSheet",
        DatasetType.ACCOUNTS_RECEIVABLE: "query",
        DatasetType.ACCOUNTS_PAYABLE: "query",
        DatasetType.AR_AGEING: "reports/AgedReceivables",
        DatasetType.AP_AGEING: "reports/AgedPayables",
        DatasetType.INVOICE_REGISTER: "query",
        DatasetType.PURCHASE_REGISTER: "query",
        DatasetType.BANK_STATEMENT: "query",
        DatasetType.CHART_OF_ACCOUNTS: "query",
        DatasetType.VENDOR_MASTER: "query",
        DatasetType.CUSTOMER_MASTER: "query",
    }

    _QUERY_TEXT: dict[DatasetType, str] = {
        DatasetType.ACCOUNTS_RECEIVABLE: "SELECT * FROM Invoice STARTPOSITION {start} MAXRESULTS {size}",
        DatasetType.ACCOUNTS_PAYABLE: "SELECT * FROM Bill STARTPOSITION {start} MAXRESULTS {size}",
        DatasetType.INVOICE_REGISTER: "SELECT * FROM Invoice STARTPOSITION {start} MAXRESULTS {size}",
        DatasetType.PURCHASE_REGISTER: "SELECT * FROM Bill STARTPOSITION {start} MAXRESULTS {size}",
        DatasetType.BANK_STATEMENT: "SELECT * FROM Deposit STARTPOSITION {start} MAXRESULTS {size}",
        DatasetType.CHART_OF_ACCOUNTS: "SELECT * FROM Account STARTPOSITION {start} MAXRESULTS {size}",
        DatasetType.VENDOR_MASTER: "SELECT * FROM Vendor STARTPOSITION {start} MAXRESULTS {size}",
        DatasetType.CUSTOMER_MASTER: "SELECT * FROM Customer STARTPOSITION {start} MAXRESULTS {size}",
    }

    def __init__(self, *, secret_store: SecretStore | None = None) -> None:
        self._secret_store = secret_store or SecretStore()

    async def test_connection(self, credentials: dict[str, Any]) -> dict[str, Any]:
        resolved = await self._resolve_credentials(credentials=credentials)
        token = await self._resolve_access_token(resolved)
        company_info = await self._request_json(
            resolved,
            endpoint=f"company/{resolved['realm_id']}/companyinfo/{resolved['realm_id']}",
            access_token=token,
            params={},
            method="GET",
        )
        return {
            "ok": True,
            "connector_type": self.connector_type.value,
            "realm_id": resolved["realm_id"],
            "company_info": company_info,
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
        start_position = int(checkpoint.get("startPosition") or kwargs.get("startPosition") or 1)
        max_results = int(checkpoint.get("maxResults") or kwargs.get("maxResults") or 1000)

        endpoint = self._DATASET_ENDPOINTS[dataset_type]
        params: dict[str, Any] = {"startPosition": start_position, "maxResults": max_results}
        method = "GET"
        body: dict[str, Any] | None = None
        if endpoint == "query":
            query_template = self._QUERY_TEXT[dataset_type]
            query = query_template.format(start=start_position, size=max_results)
            params = {}
            body = {"query": query}
            method = "POST"

        payload = await self._request_json(
            resolved,
            endpoint=f"company/{resolved['realm_id']}/{endpoint}",
            access_token=token,
            params=params,
            body=body,
            method=method,
        )
        normalized = _normalize_payload(payload)
        records = self._extract_records(dataset_type, normalized)
        next_checkpoint = self._next_checkpoint(payload=payload, start_position=start_position, max_results=max_results)
        result: dict[str, Any] = {
            "dataset_type": dataset_type.value,
            "raw_data": normalized,
            "records": records,
            "line_count": len(records),
            "erp_reported_line_count": int(payload.get("totalCount", len(records))) if isinstance(payload, dict) else len(records),
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
            for key in ("client_id", "client_secret", "refresh_token", "realm_id", "use_sandbox", "access_token"):
                if key in extra and extra[key] is not None:
                    resolved[key] = extra[key]

        for key in ("client_id", "client_secret", "realm_id"):
            if not resolved.get(key):
                raise ExtractionError(f"QuickBooks credential {key} is required")
        return resolved

    async def _resolve_access_token(self, credentials: dict[str, Any]) -> str:
        access_token = credentials.get("access_token")
        if access_token:
            return str(access_token)
        refresh_token = credentials.get("refresh_token")
        if not refresh_token:
            raise ExtractionError("QuickBooks refresh_token or access_token is required")

        data = {"grant_type": "refresh_token", "refresh_token": str(refresh_token)}
        auth = (str(credentials["client_id"]), str(credentials["client_secret"]))
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(
                "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer",
                data=data,
                auth=auth,
                headers={"Accept": "application/json"},
            )
        if response.status_code >= 400:
            raise ExtractionError(f"QuickBooks token refresh failed ({response.status_code})")
        payload = response.json()
        token = payload.get("access_token")
        if not token:
            raise ExtractionError("QuickBooks token refresh response missing access_token")
        return str(token)

    async def _request_json(
        self,
        credentials: dict[str, Any],
        *,
        endpoint: str,
        access_token: str,
        params: dict[str, Any],
        body: dict[str, Any] | None = None,
        method: str = "GET",
    ) -> dict[str, Any]:
        base = "https://sandbox-quickbooks.api.intuit.com/v3/" if bool(credentials.get("use_sandbox")) else "https://quickbooks.api.intuit.com/v3/"
        url = f"{base.rstrip('/')}/{endpoint.lstrip('/')}"
        headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
        async with httpx.AsyncClient(timeout=45.0) as client:
            if method.upper() == "POST":
                response = await client.post(url, params=params, json=body or {}, headers=headers)
            else:
                response = await client.get(url, params=params, headers=headers)
        if response.status_code >= 400:
            raise ExtractionError(f"QuickBooks API error {response.status_code} for {endpoint}")
        payload = response.json()
        if not isinstance(payload, dict):
            raise ExtractionError("QuickBooks API returned non-object payload")
        return payload

    @staticmethod
    def _extract_records(dataset_type: DatasetType, payload: Any) -> list[dict[str, Any]]:
        if not isinstance(payload, dict):
            return []
        if "QueryResponse" in payload and isinstance(payload["QueryResponse"], dict):
            query_response = payload["QueryResponse"]
            for value in query_response.values():
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
        for key in ("Rows", "rows", "records", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
            if isinstance(value, dict) and isinstance(value.get("Row"), list):
                return [item for item in value["Row"] if isinstance(item, dict)]
        if dataset_type in {DatasetType.TRIAL_BALANCE, DatasetType.PROFIT_AND_LOSS, DatasetType.BALANCE_SHEET}:
            return [payload]
        return []

    @staticmethod
    def _next_checkpoint(*, payload: Any, start_position: int, max_results: int) -> dict[str, Any] | None:
        if not isinstance(payload, dict):
            return None
        total_count = payload.get("totalCount")
        if isinstance(total_count, int):
            if start_position + max_results > total_count:
                return None
            return {"startPosition": start_position + max_results, "maxResults": max_results}
        # fallback on record count
        records = QuickbooksConnector._extract_records(DatasetType.GENERAL_LEDGER, payload)
        if len(records) < max_results:
            return None
        return {"startPosition": start_position + max_results, "maxResults": max_results}

    @staticmethod
    def _extract_control_totals(payload: Any) -> dict[str, Decimal]:
        totals: dict[str, Decimal] = {}
        if isinstance(payload, dict):
            for key, value in payload.items():
                if isinstance(value, Decimal) and any(token in key.lower() for token in ("total", "balance", "debit", "credit")):
                    totals[key] = value
        return totals
