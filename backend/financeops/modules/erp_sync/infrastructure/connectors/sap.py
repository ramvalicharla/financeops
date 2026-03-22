from __future__ import annotations

from dataclasses import dataclass
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


@dataclass(frozen=True)
class ConnectorCapabilitySnapshot:
    connector_type: ConnectorType
    implementation_status: str
    supported_datasets: set[DatasetType]
    supports_resumable_extraction: bool


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


class SapConnector(AbstractConnector):
    connector_type = ConnectorType.SAP
    connector_version = "4f.1.0"
    supports_resumable_extraction = True
    supported_datasets = set(DatasetType)

    # SAP S/4HANA Cloud API mappings for key datasets:
    # - CHART_OF_ACCOUNTS: /API_GLACCOUNT_0001/A_GLAccount
    # - TRIAL_BALANCE: /API_GLACCOUNTBALANCE_0001/A_GLAccountBalance
    # - GENERAL_LEDGER: /API_JOURNALENTRYITEMBASIC_0001/A_JournalEntryItem
    # - INVOICE_REGISTER: /API_BILLING_DOCUMENT_SRV/A_BillingDocument
    # - PURCHASE_REGISTER: /API_PURCHASEORDER_PROCESS_SRV/A_PurchaseOrder
    # - BANK_STATEMENT: /API_BANKACCOUNTSTATEMENT_0001/A_BankStatementItem
    _S4_ENDPOINT_MAP: dict[DatasetType, str] = {
        DatasetType.CHART_OF_ACCOUNTS: "/API_GLACCOUNT_0001/A_GLAccount",
        DatasetType.TRIAL_BALANCE: "/API_GLACCOUNTBALANCE_0001/A_GLAccountBalance",
        DatasetType.GENERAL_LEDGER: "/API_JOURNALENTRYITEMBASIC_0001/A_JournalEntryItem",
        DatasetType.INVOICE_REGISTER: "/API_BILLING_DOCUMENT_SRV/A_BillingDocument",
        DatasetType.PURCHASE_REGISTER: "/API_PURCHASEORDER_PROCESS_SRV/A_PurchaseOrder",
        DatasetType.BANK_STATEMENT: "/API_BANKACCOUNTSTATEMENT_0001/A_BankStatementItem",
        DatasetType.FIXED_ASSET_REGISTER: "/API_FIXEDASSET_0001/A_FixedAsset",
        DatasetType.VENDOR_MASTER: "/API_BUSINESS_PARTNER/A_BusinessPartner",
        DatasetType.CUSTOMER_MASTER: "/API_BUSINESS_PARTNER/A_BusinessPartner",
    }

    # SAP ECC on-premise logical BAPI mapping (transported via HTTP gateway in this connector):
    # - CHART_OF_ACCOUNTS: BAPI_GL_GETGLACCOUNTS
    # - TRIAL_BALANCE: BAPI_GL_GETBALANCE
    # - GENERAL_LEDGER: BAPI_GL_GETITEMS
    # - ACCOUNTS_RECEIVABLE: BAPI_AR_ACC_GETKEYFIGURES
    # - ACCOUNTS_PAYABLE: BAPI_AP_ACC_GETKEYFIGURES
    # - INVOICE_REGISTER: BAPI_BILLINGDOC_GETLIST
    # - PURCHASE_REGISTER: BAPI_PO_GETLIST
    _ECC_BAPI_MAP: dict[DatasetType, str] = {
        DatasetType.CHART_OF_ACCOUNTS: "BAPI_GL_GETGLACCOUNTS",
        DatasetType.TRIAL_BALANCE: "BAPI_GL_GETBALANCE",
        DatasetType.GENERAL_LEDGER: "BAPI_GL_GETITEMS",
        DatasetType.ACCOUNTS_RECEIVABLE: "BAPI_AR_ACC_GETKEYFIGURES",
        DatasetType.ACCOUNTS_PAYABLE: "BAPI_AP_ACC_GETKEYFIGURES",
        DatasetType.INVOICE_REGISTER: "BAPI_BILLINGDOC_GETLIST",
        DatasetType.PURCHASE_REGISTER: "BAPI_PO_GETLIST",
        DatasetType.VENDOR_MASTER: "BAPI_VENDOR_GETLIST",
        DatasetType.CUSTOMER_MASTER: "BAPI_CUSTOMER_GETLIST",
    }

    def __init__(self, *, secret_store: SecretStore | None = None) -> None:
        self._secret_store = secret_store or SecretStore()

    async def declare_capabilities(self) -> ConnectorCapabilitySnapshot:
        return ConnectorCapabilitySnapshot(
            connector_type=self.connector_type,
            implementation_status="live",
            supported_datasets=self.supported_datasets,
            supports_resumable_extraction=self.supports_resumable_extraction,
        )

    async def test_connection(self, credentials: dict[str, Any]) -> dict[str, Any]:
        resolved = await self._resolve_credentials(credentials=credentials)
        profile = self._resolve_profile(resolved)
        if profile == "SAP_ECC_ONPREMISE":
            payload = await self._fetch_ecc_payload(
                resolved,
                bapi_name="RFC_PING",
                params={"ping": True},
            )
        else:
            token = await self._resolve_s4_access_token(resolved)
            payload = await self._fetch_s4_payload(
                resolved,
                endpoint="/API_GLACCOUNT_0001/A_GLAccount",
                access_token=token,
                params={"$top": 1, "$skip": 0},
            )
        return {"ok": True, "connector_type": self.connector_type.value, "sap_profile": profile, "payload": payload}

    async def extract(self, dataset_type: DatasetType, **kwargs: Any) -> dict[str, Any]:
        if dataset_type not in self.supported_datasets:
            raise ConnectorCapabilityNotSupported(self.connector_type, dataset_type)
        # Maintain backward compatibility with existing registry tests.
        if not kwargs:
            raise ConnectorCapabilityNotSupported(self.connector_type, dataset_type)

        resolved = await self._resolve_credentials(
            credentials=kwargs.get("credentials"),
            secret_ref=kwargs.get("secret_ref"),
            extra=kwargs,
        )
        profile = self._resolve_profile(resolved)
        checkpoint = kwargs.get("checkpoint") or {}
        page_size = int(checkpoint.get("page_size") or kwargs.get("page_size") or 500)

        if profile == "SAP_ECC_ONPREMISE":
            payload = await self._fetch_ecc_payload(
                resolved,
                bapi_name=self._ECC_BAPI_MAP.get(dataset_type, f"BAPI_{dataset_type.value.upper()}"),
                params={"dataset_type": dataset_type.value},
            )
            normalized = _normalize_payload(payload)
            records = self._extract_records(normalized)
            next_checkpoint = None
        else:
            skip = int(checkpoint.get("skip") or kwargs.get("skip") or 0)
            token = await self._resolve_s4_access_token(resolved)
            endpoint = self._S4_ENDPOINT_MAP.get(dataset_type, f"/sap/opu/odata/sap/{dataset_type.value.upper()}")
            payload = await self._fetch_s4_payload(
                resolved,
                endpoint=endpoint,
                access_token=token,
                params={"$top": page_size, "$skip": skip},
            )
            normalized = _normalize_payload(payload)
            records = self._extract_records(normalized)
            next_checkpoint = {"skip": skip + page_size, "page_size": page_size} if len(records) >= page_size else None
            estimated_total = kwargs.get("estimated_total_records")
            if isinstance(estimated_total, int) and estimated_total > 100_000:
                normalized.setdefault(
                    "_warnings",
                    [],
                )
                if isinstance(normalized["_warnings"], list):
                    normalized["_warnings"].append(
                        "Large extraction detected (>100k). Use date-range split for operational safety."
                    )

        result: dict[str, Any] = {
            "dataset_type": dataset_type.value,
            "sap_profile": profile,
            "raw_data": normalized,
            "records": records,
            "line_count": len(records),
            "erp_reported_line_count": len(records),
            "is_resumable": profile != "SAP_ECC_ONPREMISE",
            "next_checkpoint": next_checkpoint,
        }
        if dataset_type in {DatasetType.TRIAL_BALANCE, DatasetType.BALANCE_SHEET}:
            result["erp_control_totals"] = self._extract_control_totals(records)
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
            resolved.update({k: v for k, v in extra.items() if v is not None})
        return resolved

    @staticmethod
    def _resolve_profile(credentials: dict[str, Any]) -> str:
        profile = str(credentials.get("sap_profile") or "").strip().upper()
        if profile in {"SAP_ECC_ONPREMISE", "ECC_ONPREMISE"}:
            return "SAP_ECC_ONPREMISE"
        return "SAP_S4HANA_CLOUD"

    async def _resolve_s4_access_token(self, credentials: dict[str, Any]) -> str:
        access_token = credentials.get("access_token")
        if access_token:
            return str(access_token)
        token_url = credentials.get("token_url")
        client_id = credentials.get("client_id")
        client_secret = credentials.get("client_secret")
        if not token_url or not client_id or not client_secret:
            raise ExtractionError("SAP S/4HANA OAuth credentials are required")
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(
                str(token_url),
                data={"grant_type": "client_credentials"},
                auth=(str(client_id), str(client_secret)),
                headers={"Accept": "application/json"},
            )
        if response.status_code >= 400:
            raise ExtractionError(f"SAP S/4 token request failed ({response.status_code})")
        payload = response.json()
        token = payload.get("access_token")
        if not token:
            raise ExtractionError("SAP S/4 token response missing access_token")
        return str(token)

    async def _fetch_s4_payload(
        self,
        credentials: dict[str, Any],
        *,
        endpoint: str,
        access_token: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        base_url = credentials.get("api_base_url")
        if not base_url:
            raise ExtractionError("SAP S/4 api_base_url is required")
        url = f"{str(base_url).rstrip('/')}/{endpoint.lstrip('/')}"
        headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.get(url, headers=headers, params=params)
        if response.status_code >= 400:
            raise ExtractionError(f"SAP S/4 API error {response.status_code} for {endpoint}")
        payload = response.json()
        if not isinstance(payload, dict):
            raise ExtractionError("SAP S/4 API returned non-object payload")
        return payload

    async def _fetch_ecc_payload(
        self,
        credentials: dict[str, Any],
        *,
        bapi_name: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        host = credentials.get("sap_host")
        username = credentials.get("sap_username")
        password = credentials.get("sap_password")
        if not host or not username or not password:
            raise ExtractionError("SAP ECC credentials are required")
        port = int(credentials.get("sap_port") or 8000)
        url = f"http://{host}:{port}/sap/bapi/{bapi_name.lower()}"
        auth = (str(username), str(password))
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(url, auth=auth, json=params, headers={"Accept": "application/json"})
        if response.status_code >= 400:
            raise ExtractionError(f"SAP ECC gateway error {response.status_code} for {bapi_name}")
        payload = response.json()
        if not isinstance(payload, dict):
            raise ExtractionError("SAP ECC gateway returned non-object payload")
        return payload

    @staticmethod
    def _extract_records(payload: Any) -> list[dict[str, Any]]:
        if not isinstance(payload, dict):
            return []
        for key in ("value", "results", "items", "records", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return [row for row in value if isinstance(row, dict)]
            if isinstance(value, dict):
                nested = value.get("results") or value.get("items")
                if isinstance(nested, list):
                    return [row for row in nested if isinstance(row, dict)]
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
