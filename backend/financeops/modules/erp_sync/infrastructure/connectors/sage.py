from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any
from xml.etree import ElementTree as ET

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


def _strip_ns(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


class SageConnector(AbstractConnector):
    connector_type = ConnectorType.SAGE
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
        DatasetType.CHART_OF_ACCOUNTS,
    }

    _SBC_ENDPOINTS: dict[DatasetType, str] = {
        DatasetType.TRIAL_BALANCE: "trial_balances",
        DatasetType.PROFIT_AND_LOSS: "profit_and_loss",
        DatasetType.BALANCE_SHEET: "balance_sheet",
        DatasetType.ACCOUNTS_RECEIVABLE: "sales_invoices",
        DatasetType.ACCOUNTS_PAYABLE: "purchase_invoices",
        DatasetType.INVOICE_REGISTER: "sales_invoices",
        DatasetType.PURCHASE_REGISTER: "purchase_invoices",
        DatasetType.CHART_OF_ACCOUNTS: "ledger_accounts",
    }

    _INTACCT_OBJECTS: dict[DatasetType, str] = {
        DatasetType.TRIAL_BALANCE: "GLTRIALBALANCE",
        DatasetType.GENERAL_LEDGER: "GLDETAIL",
        DatasetType.PROFIT_AND_LOSS: "GLSUMMARY",
        DatasetType.BALANCE_SHEET: "GLSUMMARY",
        DatasetType.ACCOUNTS_RECEIVABLE: "ARINVOICE",
        DatasetType.ACCOUNTS_PAYABLE: "APBILL",
        DatasetType.INVOICE_REGISTER: "ARINVOICE",
        DatasetType.PURCHASE_REGISTER: "APBILL",
        DatasetType.CHART_OF_ACCOUNTS: "GLACCOUNT",
    }

    def __init__(self, *, secret_store: SecretStore | None = None) -> None:
        self._secret_store = secret_store or SecretStore()

    async def test_connection(self, credentials: dict[str, Any]) -> dict[str, Any]:
        resolved = await self._resolve_credentials(credentials=credentials)
        product = self._resolve_product(resolved)
        if product == "sage_intacct":
            payload = await self._intacct_call(
                resolved,
                object_name="COMPANY",
                page_size=1,
                offset=0,
            )
        else:
            access_token = await self._resolve_sbc_access_token(resolved)
            payload = await self._sbc_request_json(
                resolved,
                endpoint="contacts",
                access_token=access_token,
                params={"page": 1},
            )
        return {"ok": True, "connector_type": self.connector_type.value, "sage_product": product, "payload": payload}

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
        product = self._resolve_product(resolved)
        checkpoint = kwargs.get("checkpoint") or {}
        page_size = int(checkpoint.get("page_size") or kwargs.get("page_size") or 100)

        if product == "sage_intacct":
            offset = int(checkpoint.get("offset") or kwargs.get("offset") or 0)
            payload = await self._intacct_call(
                resolved,
                object_name=self._INTACCT_OBJECTS[dataset_type],
                page_size=page_size,
                offset=offset,
            )
            normalized = _normalize_payload(payload)
            records = self._extract_intacct_records(normalized)
            next_checkpoint = {"offset": offset + page_size, "page_size": page_size} if len(records) >= page_size else None
        else:
            page = int(checkpoint.get("page") or kwargs.get("page") or 1)
            access_token = await self._resolve_sbc_access_token(resolved)
            payload = await self._sbc_request_json(
                resolved,
                endpoint=self._SBC_ENDPOINTS.get(dataset_type, "ledger_entries"),
                access_token=access_token,
                params={"page": page, "items_per_page": page_size},
            )
            normalized = _normalize_payload(payload)
            records = self._extract_sbc_records(normalized)
            next_checkpoint = {"page": page + 1, "page_size": page_size} if len(records) >= page_size else None

        result: dict[str, Any] = {
            "dataset_type": dataset_type.value,
            "raw_data": normalized,
            "records": records,
            "line_count": len(records),
            "erp_reported_line_count": len(records),
            "is_resumable": True,
            "next_checkpoint": next_checkpoint,
            "sage_product": product,
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
                "sage_product",
                "client_id",
                "client_secret",
                "refresh_token",
                "access_token",
                "company_id",
                "user_id",
                "user_password",
                "sender_id",
                "sender_password",
                "base_url",
            ):
                if key in extra and extra[key] is not None:
                    resolved[key] = extra[key]
        return resolved

    @staticmethod
    def _resolve_product(credentials: dict[str, Any]) -> str:
        raw = str(credentials.get("sage_product", "SAGE_BUSINESS_CLOUD")).strip().lower()
        if raw in {"sage_intacct", "intacct"}:
            return "sage_intacct"
        return "sage_business_cloud"

    async def _resolve_sbc_access_token(self, credentials: dict[str, Any]) -> str:
        access_token = credentials.get("access_token")
        if access_token:
            return str(access_token)
        refresh_token = credentials.get("refresh_token")
        if not refresh_token:
            raise ExtractionError("Sage Business Cloud access_token or refresh_token is required")
        if not credentials.get("client_id") or not credentials.get("client_secret"):
            raise ExtractionError("Sage Business Cloud client_id and client_secret are required")
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(
                "https://oauth.accounting.sage.com/token",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": str(refresh_token),
                    "client_id": str(credentials["client_id"]),
                    "client_secret": str(credentials["client_secret"]),
                },
                headers={"Accept": "application/json"},
            )
        if response.status_code >= 400:
            raise ExtractionError(f"Sage Business Cloud token refresh failed ({response.status_code})")
        payload = response.json()
        token = payload.get("access_token")
        if not token:
            raise ExtractionError("Sage Business Cloud token response missing access_token")
        return str(token)

    async def _sbc_request_json(
        self,
        credentials: dict[str, Any],
        *,
        endpoint: str,
        access_token: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        base_url = str(credentials.get("base_url") or "https://api.accounting.sage.com/v3.1")
        url = f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.get(url, headers=headers, params=params)
        if response.status_code >= 400:
            raise ExtractionError(f"Sage Business Cloud API error {response.status_code} for {endpoint}")
        payload = response.json()
        if not isinstance(payload, dict):
            raise ExtractionError("Sage Business Cloud API returned non-object payload")
        return payload

    async def _intacct_call(
        self,
        credentials: dict[str, Any],
        *,
        object_name: str,
        page_size: int,
        offset: int,
    ) -> dict[str, Any]:
        required = ("company_id", "user_id", "user_password", "sender_id", "sender_password")
        missing = [field for field in required if not credentials.get(field)]
        if missing:
            raise ExtractionError(f"Sage Intacct credentials missing: {', '.join(missing)}")
        xml_request = (
            "<request><control>"
            f"<senderid>{credentials['sender_id']}</senderid>"
            f"<password>{credentials['sender_password']}</password>"
            "</control><operation><authentication>"
            f"<login><userid>{credentials['user_id']}</userid>"
            f"<companyid>{credentials['company_id']}</companyid>"
            f"<password>{credentials['user_password']}</password></login>"
            "</authentication><content><function controlid=\"f1\">"
            f"<readByQuery><object>{object_name}</object><fields>*</fields>"
            "<query></query>"
            f"<pagesize>{page_size}</pagesize><offset>{offset}</offset>"
            "</readByQuery></function></content></operation></request>"
        )
        endpoint = str(credentials.get("base_url") or "https://api.intacct.com/ia/xml/xmlgw.phtml")
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(
                endpoint,
                content=xml_request.encode("utf-8"),
                headers={"Content-Type": "application/xml", "Accept": "application/xml"},
            )
        if response.status_code >= 400:
            raise ExtractionError(f"Sage Intacct API error {response.status_code}")
        root = ET.fromstring(response.text)
        return self._xml_to_dict(root)

    def _xml_to_dict(self, element: ET.Element) -> dict[str, Any]:
        children = list(element)
        if not children:
            return {_strip_ns(element.tag): _to_decimal_if_numeric((element.text or "").strip())}
        payload: dict[str, Any] = {}
        for child in children:
            key = _strip_ns(child.tag)
            child_payload = self._xml_to_dict(child)
            value = child_payload.get(key)
            if key in payload:
                if not isinstance(payload[key], list):
                    payload[key] = [payload[key]]
                payload[key].append(value)
            else:
                payload[key] = value
        return {_strip_ns(element.tag): payload}

    @staticmethod
    def _extract_sbc_records(payload: Any) -> list[dict[str, Any]]:
        if not isinstance(payload, dict):
            return []
        for key in ("$items", "items", "data", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
            if isinstance(value, dict):
                nested = value.get("$items") or value.get("items")
                if isinstance(nested, list):
                    return [item for item in nested if isinstance(item, dict)]
        return []

    @staticmethod
    def _extract_intacct_records(payload: Any) -> list[dict[str, Any]]:
        if not isinstance(payload, dict):
            return []
        records: list[dict[str, Any]] = []

        def walk(node: Any) -> None:
            if isinstance(node, dict):
                if any(key.lower() == "record" for key in node):
                    record = node.get("record")
                    if isinstance(record, dict):
                        records.append(record)
                    elif isinstance(record, list):
                        records.extend([item for item in record if isinstance(item, dict)])
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for item in node:
                    walk(item)

        walk(payload)
        return records

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
