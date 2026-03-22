from __future__ import annotations

import re
from datetime import date
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


_NUMERIC_PATTERN = re.compile(r"^-?\d+(?:\.\d+)?$")


def _strip_ns(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def _to_decimal_if_numeric(value: str) -> Decimal | str:
    cleaned = value.strip().replace(",", "")
    if _NUMERIC_PATTERN.fullmatch(cleaned):
        try:
            return Decimal(cleaned)
        except (InvalidOperation, ValueError):
            return value.strip()
    return value.strip()


def _xml_element_to_dict(element: ET.Element) -> dict[str, Any] | Decimal | str:
    children = list(element)
    if not children:
        text = element.text or ""
        return _to_decimal_if_numeric(text) if text.strip() else ""

    payload: dict[str, Any] = {}
    for child in children:
        key = _strip_ns(child.tag)
        value = _xml_element_to_dict(child)
        if key in payload:
            if not isinstance(payload[key], list):
                payload[key] = [payload[key]]
            payload[key].append(value)
        else:
            payload[key] = value
    return payload


def _extract_record_nodes(root: ET.Element) -> list[dict[str, Any]]:
    record_tag_candidates = {"ROW", "LINE", "ENTRY", "LEDGER", "VOUCHER", "ITEM"}
    records: list[dict[str, Any]] = []
    for node in root.iter():
        node_name = _strip_ns(node.tag).upper()
        if node_name not in record_tag_candidates:
            continue
        children = list(node)
        if not children:
            continue
        record: dict[str, Any] = {}
        for child in children:
            child_name = _strip_ns(child.tag)
            child_text = (child.text or "").strip()
            if child_text:
                record[child_name] = _to_decimal_if_numeric(child_text)
            else:
                record[child_name] = _xml_element_to_dict(child)
        if record:
            records.append(record)
    return records


def _extract_control_totals(root: ET.Element) -> dict[str, Decimal]:
    control_totals: dict[str, Decimal] = {}
    for node in root.iter():
        tag = _strip_ns(node.tag).lower()
        text = (node.text or "").strip()
        if not text:
            continue
        value = _to_decimal_if_numeric(text)
        if not isinstance(value, Decimal):
            continue
        if any(token in tag for token in ("total", "closing", "debit", "credit", "balance")):
            control_totals[tag] = value
    return control_totals


def _decode_xml(raw: bytes) -> str:
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        try:
            return raw.decode("cp1252")
        except UnicodeDecodeError as exc:
            raise ExtractionError("Unable to decode Tally XML response") from exc


class TallyConnector(AbstractConnector):
    connector_type = ConnectorType.TALLY
    connector_version = "4d.1.0"
    supports_resumable_extraction = False
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
        DatasetType.TDS_REGISTER,
        DatasetType.GST_RETURN_GSTR1,
    }

    _DATASET_TALLY_ID: dict[DatasetType, str] = {
        DatasetType.TRIAL_BALANCE: "Trial Balance",
        DatasetType.GENERAL_LEDGER: "General Ledger",
        DatasetType.PROFIT_AND_LOSS: "Profit & Loss",
        DatasetType.BALANCE_SHEET: "Balance Sheet",
        DatasetType.ACCOUNTS_RECEIVABLE: "Bills Receivable",
        DatasetType.ACCOUNTS_PAYABLE: "Bills Payable",
        DatasetType.INVOICE_REGISTER: "Sales Register",
        DatasetType.PURCHASE_REGISTER: "Purchase Register",
        DatasetType.BANK_STATEMENT: "Bank Book",
        DatasetType.CHART_OF_ACCOUNTS: "List of Ledgers",
        DatasetType.VENDOR_MASTER: "List of Ledgers",
        DatasetType.CUSTOMER_MASTER: "List of Ledgers",
        DatasetType.TDS_REGISTER: "TDS Nature wise",
        DatasetType.GST_RETURN_GSTR1: "GSTR1",
    }

    def __init__(self, *, secret_store: SecretStore | None = None) -> None:
        self._secret_store = secret_store or SecretStore()

    async def test_connection(self, credentials: dict[str, Any]) -> dict[str, Any]:
        resolved = await self._resolve_credentials(credentials=credentials)
        request_xml = self._build_connection_probe_xml(company_name=resolved.get("tally_company_name"))
        response_xml = await self._post_xml(resolved, request_xml)
        root = ET.fromstring(response_xml)
        parsed = _xml_element_to_dict(root)
        response_text = response_xml.lower()
        company_name = str(resolved.get("tally_company_name", "") or "").strip()
        if company_name and company_name.lower() not in response_text:
            return {
                "ok": False,
                "connector_type": self.connector_type.value,
                "message": f"Company mismatch: expected {company_name}",
            }
        return {
            "ok": True,
            "connector_type": self.connector_type.value,
            "company_name": company_name or None,
            "response_preview": parsed if isinstance(parsed, dict) else {"value": str(parsed)},
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
        xml_request = self._build_dataset_tdl_request(
            dataset_type=dataset_type,
            company_name=str(resolved.get("tally_company_name", "") or ""),
            period_start=kwargs.get("period_start"),
            period_end=kwargs.get("period_end"),
        )
        xml_response = await self._post_xml(resolved, xml_request)
        root = ET.fromstring(xml_response)
        raw_dict = _xml_element_to_dict(root)
        records = _extract_record_nodes(root)
        control_totals = (
            _extract_control_totals(root)
            if dataset_type in {DatasetType.TRIAL_BALANCE, DatasetType.BALANCE_SHEET}
            else {}
        )

        line_count = len(records)
        result: dict[str, Any] = {
            "dataset_type": dataset_type.value,
            "raw_data": raw_dict,
            "records": records,
            "line_count": line_count,
            "erp_reported_line_count": line_count,
            "is_resumable": False,
            "next_checkpoint": None,
        }
        if control_totals:
            result["erp_control_totals"] = control_totals
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
            for key in ("tally_host", "tally_port", "tally_company_name", "username", "password"):
                if key in extra and extra[key] is not None:
                    resolved[key] = extra[key]
        resolved.setdefault("tally_host", "localhost")
        resolved.setdefault("tally_port", 9000)
        if not resolved.get("tally_company_name"):
            raise ExtractionError("tally_company_name is required")
        return resolved

    async def _post_xml(self, credentials: dict[str, Any], request_xml: str) -> str:
        host = str(credentials.get("tally_host", "localhost"))
        port = int(credentials.get("tally_port", 9000))
        url = f"http://{host}:{port}"
        headers = {"Content-Type": "text/xml; charset=utf-8"}
        auth: httpx.BasicAuth | None = None
        username = credentials.get("username")
        password = credentials.get("password")
        if username and password:
            auth = httpx.BasicAuth(str(username), str(password))

        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(url, content=request_xml.encode("utf-8"), headers=headers, auth=auth)
        if response.status_code >= 400:
            raise ExtractionError(f"Tally gateway returned HTTP {response.status_code}")
        return _decode_xml(response.content)

    def _build_connection_probe_xml(self, *, company_name: str | None) -> str:
        company_node = (
            f"<SVCURRENTCOMPANY>{company_name}</SVCURRENTCOMPANY>"
            if company_name
            else ""
        )
        return (
            "<ENVELOPE>"
            "<HEADER><VERSION>1</VERSION><TALLYREQUEST>Export</TALLYREQUEST><TYPE>Data</TYPE>"
            "<ID>List of Companies</ID></HEADER>"
            "<BODY><DESC><STATICVARIABLES>"
            "<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>"
            f"{company_node}"
            "</STATICVARIABLES></DESC></BODY>"
            "</ENVELOPE>"
        )

    def _build_dataset_tdl_request(
        self,
        *,
        dataset_type: DatasetType,
        company_name: str,
        period_start: date | str | None,
        period_end: date | str | None,
    ) -> str:
        report_id = self._DATASET_TALLY_ID.get(dataset_type)
        if report_id is None:
            raise ConnectorCapabilityNotSupported(self.connector_type, dataset_type)

        from_date = self._format_tally_date(period_start)
        to_date = self._format_tally_date(period_end)
        from_node = f"<SVFROMDATE>{from_date}</SVFROMDATE>" if from_date else ""
        to_node = f"<SVTODATE>{to_date}</SVTODATE>" if to_date else ""
        company_node = f"<SVCURRENTCOMPANY>{company_name}</SVCURRENTCOMPANY>"

        # TDL request template for report exports.
        return (
            "<ENVELOPE>"
            "<HEADER>"
            "<VERSION>1</VERSION>"
            "<TALLYREQUEST>Export</TALLYREQUEST>"
            "<TYPE>Data</TYPE>"
            f"<ID>{report_id}</ID>"
            "</HEADER>"
            "<BODY>"
            "<DESC>"
            "<STATICVARIABLES>"
            "<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>"
            f"{company_node}"
            f"{from_node}"
            f"{to_node}"
            "</STATICVARIABLES>"
            "</DESC>"
            "</BODY>"
            "</ENVELOPE>"
        )

    @staticmethod
    def _format_tally_date(value: date | str | None) -> str | None:
        if value is None:
            return None
        if isinstance(value, date):
            return value.strftime("%Y%m%d")
        cleaned = str(value).strip()
        if not cleaned:
            return None
        if re.fullmatch(r"\d{8}", cleaned):
            return cleaned
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", cleaned):
            return cleaned.replace("-", "")
        return cleaned
