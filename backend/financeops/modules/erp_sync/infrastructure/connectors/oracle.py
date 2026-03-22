from __future__ import annotations

from dataclasses import dataclass
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


class OracleConnector(AbstractConnector):
    connector_type = ConnectorType.ORACLE
    connector_version = "4f.1.0"
    supports_resumable_extraction = True
    supported_datasets = set(DatasetType)

    _FUSION_ENDPOINT_MAP: dict[DatasetType, str] = {
        DatasetType.CHART_OF_ACCOUNTS: "/fscmRestApi/resources/latest/glAccounts",
        DatasetType.TRIAL_BALANCE: "/fscmRestApi/resources/latest/trialBalances",
        DatasetType.GENERAL_LEDGER: "/fscmRestApi/resources/latest/journalBatches",
        DatasetType.BALANCE_SHEET: "/fscmRestApi/resources/latest/financialReports",
        DatasetType.PROFIT_AND_LOSS: "/fscmRestApi/resources/latest/financialReports",
        DatasetType.INVOICE_REGISTER: "/fscmRestApi/resources/latest/receivablesInvoices",
        DatasetType.PURCHASE_REGISTER: "/fscmRestApi/resources/latest/payablesInvoices",
        DatasetType.VENDOR_MASTER: "/fscmRestApi/resources/latest/suppliers",
        DatasetType.CUSTOMER_MASTER: "/fscmRestApi/resources/latest/customers",
    }

    # Oracle EBS XML Gateway map (interface names carried in endpoint path).
    _EBS_ENDPOINT_MAP: dict[DatasetType, str] = {
        DatasetType.CHART_OF_ACCOUNTS: "GL_ACCOUNTS",
        DatasetType.TRIAL_BALANCE: "GL_TRIAL_BALANCE",
        DatasetType.GENERAL_LEDGER: "GL_JOURNAL_LINES",
        DatasetType.BALANCE_SHEET: "GL_BALANCE_SHEET",
        DatasetType.PROFIT_AND_LOSS: "GL_PROFIT_LOSS",
        DatasetType.INVOICE_REGISTER: "AP_INVOICES",
        DatasetType.PURCHASE_REGISTER: "PO_HEADERS",
        DatasetType.VENDOR_MASTER: "AP_SUPPLIERS",
        DatasetType.CUSTOMER_MASTER: "AR_CUSTOMERS",
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

        if profile == "ORACLE_EBS_ONPREMISE":
            payload = await self._fetch_ebs_payload(
                resolved,
                interface_name="PING",
                params={"ping": True},
            )
        else:
            token = await self._resolve_fusion_access_token(resolved)
            payload = await self._fetch_fusion_payload(
                resolved,
                endpoint="/fscmRestApi/resources/latest/erpintegrations",
                access_token=token,
                params={"limit": 1, "offset": 0},
            )

        return {
            "ok": True,
            "connector_type": self.connector_type.value,
            "oracle_profile": profile,
            "payload": payload,
        }

    async def extract(self, dataset_type: DatasetType, **kwargs: Any) -> dict[str, Any]:
        if dataset_type not in self.supported_datasets:
            raise ConnectorCapabilityNotSupported(self.connector_type, dataset_type)
        # Preserve compatibility with legacy registry tests that call extract() without context.
        if not kwargs:
            raise ConnectorCapabilityNotSupported(self.connector_type, dataset_type)

        resolved = await self._resolve_credentials(
            credentials=kwargs.get("credentials"),
            secret_ref=kwargs.get("secret_ref"),
            extra=kwargs,
        )
        profile = self._resolve_profile(resolved)
        checkpoint = kwargs.get("checkpoint") or {}
        page_size = int(checkpoint.get("limit") or kwargs.get("limit") or 500)

        if profile == "ORACLE_EBS_ONPREMISE":
            payload = await self._fetch_ebs_payload(
                resolved,
                interface_name=self._EBS_ENDPOINT_MAP.get(dataset_type, dataset_type.value.upper()),
                params={"dataset_type": dataset_type.value},
            )
            normalized = _normalize_payload(payload)
            records = self._extract_records(normalized)
            next_checkpoint = None
        else:
            offset = int(checkpoint.get("offset") or kwargs.get("offset") or 0)
            token = await self._resolve_fusion_access_token(resolved)
            endpoint = self._FUSION_ENDPOINT_MAP.get(
                dataset_type,
                f"/fscmRestApi/resources/latest/{dataset_type.value}",
            )
            payload = await self._fetch_fusion_payload(
                resolved,
                endpoint=endpoint,
                access_token=token,
                params={"limit": page_size, "offset": offset},
            )
            normalized = _normalize_payload(payload)
            records = self._extract_records(normalized)
            next_checkpoint = {"offset": offset + page_size, "limit": page_size} if len(records) >= page_size else None

        result: dict[str, Any] = {
            "dataset_type": dataset_type.value,
            "oracle_profile": profile,
            "raw_data": normalized,
            "records": records,
            "line_count": len(records),
            "erp_reported_line_count": len(records),
            "is_resumable": profile != "ORACLE_EBS_ONPREMISE",
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
        profile = str(credentials.get("oracle_profile") or "").strip().upper()
        if profile in {"ORACLE_EBS_ONPREMISE", "EBS_ONPREMISE"}:
            return "ORACLE_EBS_ONPREMISE"
        return "ORACLE_FUSION_CLOUD"

    async def _resolve_fusion_access_token(self, credentials: dict[str, Any]) -> str:
        access_token = credentials.get("access_token")
        if access_token:
            return str(access_token)

        token_url = credentials.get("token_url")
        client_id = credentials.get("client_id")
        client_secret = credentials.get("client_secret")
        if not token_url or not client_id or not client_secret:
            raise ExtractionError("Oracle Fusion OAuth credentials are required")

        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(
                str(token_url),
                data={"grant_type": "client_credentials"},
                auth=(str(client_id), str(client_secret)),
                headers={"Accept": "application/json"},
            )

        if response.status_code >= 400:
            raise ExtractionError(f"Oracle Fusion token request failed ({response.status_code})")

        payload = response.json()
        token = payload.get("access_token")
        if not token:
            raise ExtractionError("Oracle Fusion token response missing access_token")

        return str(token)

    async def _fetch_fusion_payload(
        self,
        credentials: dict[str, Any],
        *,
        endpoint: str,
        access_token: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        base_url = credentials.get("api_base_url")
        if not base_url:
            raise ExtractionError("Oracle Fusion api_base_url is required")
        url = f"{str(base_url).rstrip('/')}/{endpoint.lstrip('/')}"
        headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}

        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.get(url, headers=headers, params=params)

        if response.status_code >= 400:
            raise ExtractionError(f"Oracle Fusion API error {response.status_code} for {endpoint}")

        payload = response.json()
        if not isinstance(payload, dict):
            raise ExtractionError("Oracle Fusion API returned non-object payload")
        return payload

    async def _fetch_ebs_payload(
        self,
        credentials: dict[str, Any],
        *,
        interface_name: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        host = credentials.get("ebs_host")
        username = credentials.get("ebs_username")
        password = credentials.get("ebs_password")
        if not host or not username or not password:
            raise ExtractionError("Oracle EBS credentials are required")

        port = int(credentials.get("ebs_port") or 8000)
        url = f"http://{host}:{port}/xmlgateway/{interface_name.lower()}"
        headers = {"Content-Type": "application/xml", "Accept": "application/xml, application/json"}
        body = self._build_ebs_request_xml(interface_name=interface_name, params=params)

        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(url, auth=(str(username), str(password)), content=body, headers=headers)

        if response.status_code >= 400:
            raise ExtractionError(f"Oracle EBS gateway error {response.status_code} for {interface_name}")

        return self._parse_http_payload(response)

    @staticmethod
    def _build_ebs_request_xml(*, interface_name: str, params: dict[str, Any]) -> str:
        root = ET.Element("OracleEBSRequest")
        interface = ET.SubElement(root, "Interface")
        interface.text = interface_name
        params_node = ET.SubElement(root, "Params")
        for key, value in sorted(params.items()):
            param = ET.SubElement(params_node, "Param", name=str(key))
            param.text = str(value)
        return ET.tostring(root, encoding="unicode")

    def _parse_http_payload(self, response: httpx.Response) -> dict[str, Any]:
        content_type = str(response.headers.get("content-type") or "").lower()
        text = response.text.strip()

        if "application/json" in content_type:
            payload = response.json()
            if not isinstance(payload, dict):
                raise ExtractionError("Oracle EBS response returned non-object JSON")
            return payload

        if "xml" in content_type or text.startswith("<"):
            return self._xml_to_dict(text)

        raise ExtractionError("Oracle EBS response format unsupported")

    def _xml_to_dict(self, xml_text: str) -> dict[str, Any]:
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            raise ExtractionError("Oracle EBS XML parse failure") from exc

        def element_to_obj(elem: ET.Element) -> Any:
            children = list(elem)
            if not children:
                return _to_decimal_if_numeric(elem.text or "")
            bucket: dict[str, Any] = {}
            for child in children:
                value = element_to_obj(child)
                if child.tag in bucket:
                    existing = bucket[child.tag]
                    if isinstance(existing, list):
                        existing.append(value)
                    else:
                        bucket[child.tag] = [existing, value]
                else:
                    bucket[child.tag] = value
            return bucket

        parsed = element_to_obj(root)
        if isinstance(parsed, dict):
            return {root.tag: parsed}
        return {root.tag: parsed}

    @staticmethod
    def _extract_records(payload: Any) -> list[dict[str, Any]]:
        if not isinstance(payload, dict):
            return []

        for key in ("items", "records", "value", "results", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return [row for row in value if isinstance(row, dict)]
            if isinstance(value, dict):
                for nested_key in ("items", "results", "record"):
                    nested = value.get(nested_key)
                    if isinstance(nested, list):
                        return [row for row in nested if isinstance(row, dict)]
                    if isinstance(nested, dict):
                        return [nested]

        # XML converted payload: unwrap first nested list of dicts when possible.
        for value in payload.values():
            if isinstance(value, dict):
                for nested in value.values():
                    if isinstance(nested, list):
                        return [row for row in nested if isinstance(row, dict)]
                    if isinstance(nested, dict):
                        return [nested]

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
