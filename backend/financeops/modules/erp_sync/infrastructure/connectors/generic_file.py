from __future__ import annotations

import csv
import io
import json
from typing import Any

import pandas as pd

from financeops.modules.erp_sync.domain.enums import ConnectorType, DatasetType
from financeops.modules.erp_sync.infrastructure.connectors.base import AbstractConnector, ExtractionError


class GenericFileConnector(AbstractConnector):
    connector_type = ConnectorType.GENERIC_FILE
    connector_version = "1.0.0"
    supported_datasets = {
        DatasetType.CHART_OF_ACCOUNTS,
        DatasetType.TRIAL_BALANCE,
        DatasetType.GENERAL_LEDGER,
        DatasetType.VENDOR_MASTER,
        DatasetType.CUSTOMER_MASTER,
        DatasetType.DIMENSION_MASTER,
        DatasetType.CURRENCY_MASTER,
    }
    supports_resumable_extraction = True

    async def test_connection(self, credentials: dict[str, Any]) -> dict[str, Any]:
        try:
            filename = str(
                credentials.get("filename")
                or credentials.get("file_name")
                or credentials.get("sample_filename")
                or "connection-check.csv"
            )
            lower = filename.lower()
            if not lower.endswith((".csv", ".json", ".xlsx", ".xls")):
                raise ExtractionError(f"Unsupported file format: {filename}")
            return {
                "ok": True,
                "latency_ms": 0,
                "connector_type": self.connector_type.value,
            }
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def _parse_records(self, *, content: bytes, filename: str) -> list[dict[str, Any]]:
        lower = filename.lower()
        if lower.endswith(".json"):
            parsed = json.loads(content.decode("utf-8"))
            if isinstance(parsed, list):
                return [item for item in parsed if isinstance(item, dict)]
            if isinstance(parsed, dict):
                return [parsed]
            return []
        if lower.endswith(".csv"):
            text_data = content.decode("utf-8")
            reader = csv.DictReader(io.StringIO(text_data))
            return [dict(row) for row in reader]
        if lower.endswith(".xlsx") or lower.endswith(".xls"):
            df = pd.read_excel(io.BytesIO(content))
            return [dict(row) for row in df.to_dict(orient="records")]
        raise ExtractionError(f"Unsupported file format: {filename}")

    def _summary(self, records: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "line_count": len(records),
            "erp_reported_line_count": len(records),
        }

    async def extract_chart_of_accounts(self, **kwargs: Any) -> dict[str, Any]:
        content = kwargs.get("content")
        filename = kwargs.get("filename", "data.csv")
        if not isinstance(content, (bytes, bytearray)):
            raise ExtractionError("content bytes are required for generic_file extraction")
        records = self._parse_records(content=bytes(content), filename=str(filename))
        return {"dataset_type": DatasetType.CHART_OF_ACCOUNTS.value, "records": records, **self._summary(records)}

    async def extract_trial_balance(self, **kwargs: Any) -> dict[str, Any]:
        content = kwargs.get("content")
        filename = kwargs.get("filename", "data.csv")
        if not isinstance(content, (bytes, bytearray)):
            raise ExtractionError("content bytes are required for generic_file extraction")
        records = self._parse_records(content=bytes(content), filename=str(filename))
        return {"dataset_type": DatasetType.TRIAL_BALANCE.value, "records": records, **self._summary(records)}

    async def extract_general_ledger(self, **kwargs: Any) -> dict[str, Any]:
        content = kwargs.get("content")
        filename = kwargs.get("filename", "data.csv")
        if not isinstance(content, (bytes, bytearray)):
            raise ExtractionError("content bytes are required for generic_file extraction")
        records = self._parse_records(content=bytes(content), filename=str(filename))
        return {"dataset_type": DatasetType.GENERAL_LEDGER.value, "records": records, **self._summary(records)}
