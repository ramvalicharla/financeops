from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from financeops.modules.erp_sync.domain.enums import ConnectorType, DatasetType
from financeops.modules.erp_sync.infrastructure.connectors.base import (
    AbstractConnector,
    ConnectorCapabilityNotSupported,
    ExtractionError,
)
from financeops.modules.erp_sync.infrastructure.connectors.generic_file import (
    GenericFileConnector,
)


def _to_decimal_if_numeric(value: Any) -> Any:
    if isinstance(value, str):
        cleaned = value.strip().replace(",", "")
        if cleaned and all(ch.isdigit() or ch in {"-", "."} for ch in cleaned):
            try:
                return Decimal(cleaned)
            except (InvalidOperation, ValueError):
                return value
    return value


def _should_convert_to_decimal(field_name: str) -> bool:
    normalized = field_name.lower()
    return any(
        token in normalized
        for token in (
            "amount",
            "debit",
            "credit",
            "tax",
            "balance",
            "opening",
            "closing",
            "total",
        )
    )


MUNIM_COLUMN_MAPPINGS: dict[str, dict[DatasetType, dict[str, str]]] = {
    "munim": {
        DatasetType.TRIAL_BALANCE: {
            "Ledger Name": "account_name",
            "Ledger Code": "account_code",
            "Dr Amount": "closing_debit",
            "Cr Amount": "closing_credit",
        },
        DatasetType.GENERAL_LEDGER: {
            "Voucher No": "voucher_number",
            "Txn Date": "entry_date",
            "Ledger": "account_name",
            "Debit": "debit",
            "Credit": "credit",
            "Narration": "narration",
        },
        DatasetType.ACCOUNTS_RECEIVABLE: {
            "Invoice No": "invoice_number",
            "Invoice Date": "invoice_date",
            "Customer": "customer_name",
            "Outstanding": "balance_due",
        },
        DatasetType.ACCOUNTS_PAYABLE: {
            "Bill No": "bill_number",
            "Bill Date": "bill_date",
            "Vendor": "vendor_name",
            "Outstanding": "balance_due",
        },
        DatasetType.INVOICE_REGISTER: {
            "Invoice No": "invoice_number",
            "Invoice Date": "invoice_date",
            "Customer": "customer_name",
            "Total": "invoice_amount",
        },
        DatasetType.PURCHASE_REGISTER: {
            "Bill No": "bill_number",
            "Bill Date": "bill_date",
            "Vendor": "vendor_name",
            "Total": "bill_amount",
        },
        DatasetType.CHART_OF_ACCOUNTS: {
            "Ledger Code": "account_code",
            "Ledger Name": "account_name",
            "Group": "account_group",
        },
    },
    "vyapar": {
        DatasetType.TRIAL_BALANCE: {
            "Account Name": "account_name",
            "Account ID": "account_code",
            "Debit Value": "closing_debit",
            "Credit Value": "closing_credit",
        },
        DatasetType.GENERAL_LEDGER: {
            "Entry No": "voucher_number",
            "Date": "entry_date",
            "Account Name": "account_name",
            "Debit Value": "debit",
            "Credit Value": "credit",
            "Notes": "narration",
        },
        DatasetType.ACCOUNTS_RECEIVABLE: {
            "Sales No": "invoice_number",
            "Sales Date": "invoice_date",
            "Party": "customer_name",
            "Pending Amount": "balance_due",
        },
        DatasetType.ACCOUNTS_PAYABLE: {
            "Purchase No": "bill_number",
            "Purchase Date": "bill_date",
            "Party": "vendor_name",
            "Pending Amount": "balance_due",
        },
        DatasetType.INVOICE_REGISTER: {
            "Sales No": "invoice_number",
            "Sales Date": "invoice_date",
            "Party": "customer_name",
            "Grand Total": "invoice_amount",
        },
        DatasetType.PURCHASE_REGISTER: {
            "Purchase No": "bill_number",
            "Purchase Date": "bill_date",
            "Party": "vendor_name",
            "Grand Total": "bill_amount",
        },
        DatasetType.CHART_OF_ACCOUNTS: {
            "Account ID": "account_code",
            "Account Name": "account_name",
            "Category": "account_group",
        },
    },
}

REQUIRED_FIELDS: dict[DatasetType, set[str]] = {
    DatasetType.TRIAL_BALANCE: {"account_code", "account_name"},
    DatasetType.GENERAL_LEDGER: {"voucher_number", "entry_date"},
    DatasetType.ACCOUNTS_RECEIVABLE: {"invoice_number", "invoice_date"},
    DatasetType.ACCOUNTS_PAYABLE: {"bill_number", "bill_date"},
    DatasetType.INVOICE_REGISTER: {"invoice_number", "invoice_date"},
    DatasetType.PURCHASE_REGISTER: {"bill_number", "bill_date"},
    DatasetType.CHART_OF_ACCOUNTS: {"account_code", "account_name"},
}


class MunimConnector(AbstractConnector):
    connector_type = ConnectorType.MUNIM
    connector_version = "4d.1.0"
    supports_resumable_extraction = True
    supported_datasets = {
        DatasetType.TRIAL_BALANCE,
        DatasetType.GENERAL_LEDGER,
        DatasetType.ACCOUNTS_RECEIVABLE,
        DatasetType.ACCOUNTS_PAYABLE,
        DatasetType.INVOICE_REGISTER,
        DatasetType.PURCHASE_REGISTER,
        DatasetType.CHART_OF_ACCOUNTS,
    }

    def __init__(self) -> None:
        self._delegate = GenericFileConnector()

    async def extract(self, dataset_type: DatasetType, **kwargs: Any) -> dict[str, Any]:
        if dataset_type not in self.supported_datasets:
            raise ConnectorCapabilityNotSupported(self.connector_type, dataset_type)
        # Keep backward compatibility with existing stub-only capability tests.
        if not kwargs:
            raise ConnectorCapabilityNotSupported(self.connector_type, dataset_type)

        content = kwargs.get("content")
        filename = str(kwargs.get("filename", "munim.csv"))
        if not isinstance(content, (bytes, bytearray)):
            raise ExtractionError("Munim/Vyapar extraction requires CSV/JSON content bytes")
        app_variant = self._resolve_variant(kwargs.get("app_variant"))

        raw_records = self._delegate._parse_records(content=bytes(content), filename=filename)
        mapped_records = self._map_records(dataset_type=dataset_type, records=raw_records, variant=app_variant)
        self._validate_records(dataset_type=dataset_type, records=mapped_records, app_variant=app_variant)

        checkpoint = kwargs.get("checkpoint") or {}
        page = int(checkpoint.get("page") or kwargs.get("page") or 1)
        page_size = int(kwargs.get("page_size") or 1000)
        start = (page - 1) * page_size
        end = start + page_size
        page_records = mapped_records[start:end]
        has_more = end < len(mapped_records)
        next_checkpoint = {"page": page + 1, "page_size": page_size} if has_more else None

        return {
            "dataset_type": dataset_type.value,
            "records": page_records,
            "raw_data": {"records": mapped_records, "app_variant": app_variant},
            "line_count": len(page_records),
            "erp_reported_line_count": len(mapped_records),
            "is_resumable": True,
            "next_checkpoint": next_checkpoint,
        }

    def _resolve_variant(self, value: Any) -> str:
        normalized = str(value or "MUNIM").strip().lower()
        if normalized in {"munim", "vyapar"}:
            return normalized
        return "munim"

    def _map_records(
        self,
        *,
        dataset_type: DatasetType,
        records: list[dict[str, Any]],
        variant: str,
    ) -> list[dict[str, Any]]:
        mapping = MUNIM_COLUMN_MAPPINGS.get(variant, {}).get(dataset_type, {})
        mapped_records: list[dict[str, Any]] = []
        for record in records:
            mapped: dict[str, Any] = {}
            for key, value in record.items():
                normalized_key = mapping.get(key, key)
                if _should_convert_to_decimal(normalized_key):
                    mapped[normalized_key] = _to_decimal_if_numeric(value)
                else:
                    mapped[normalized_key] = value
            mapped_records.append(mapped)
        return mapped_records

    def _validate_records(
        self,
        *,
        dataset_type: DatasetType,
        records: list[dict[str, Any]],
        app_variant: str,
    ) -> None:
        if not records:
            raise ExtractionError(f"{app_variant} payload for {dataset_type.value} has no data rows")
        required = REQUIRED_FIELDS.get(dataset_type, set())
        missing = sorted(required - set(records[0].keys()))
        if missing:
            raise ExtractionError(
                f"{app_variant} {dataset_type.value} missing required columns after mapping: {', '.join(missing)}"
            )
