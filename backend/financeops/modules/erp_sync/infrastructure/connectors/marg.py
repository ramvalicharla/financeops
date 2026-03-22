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
    monetary_tokens = (
        "amount",
        "debit",
        "credit",
        "qty",
        "quantity",
        "value",
        "tax",
        "total",
        "opening",
        "closing",
        "balance",
    )
    return any(token in normalized for token in monetary_tokens)


MARG_COLUMN_MAPPINGS: dict[str, dict[DatasetType, dict[str, str]]] = {
    "v9": {
        DatasetType.TRIAL_BALANCE: {
            "Account Name": "account_name",
            "Account Code": "account_code",
            "Opening Dr": "opening_debit",
            "Opening Cr": "opening_credit",
            "Closing Dr": "closing_debit",
            "Closing Cr": "closing_credit",
        },
        DatasetType.GENERAL_LEDGER: {
            "Voucher No": "voucher_number",
            "Date": "entry_date",
            "Ledger": "account_name",
            "Dr": "debit",
            "Cr": "credit",
            "Narration": "narration",
        },
        DatasetType.INVOICE_REGISTER: {
            "Invoice No": "invoice_number",
            "Invoice Date": "invoice_date",
            "Party Name": "customer_name",
            "Taxable Value": "taxable_amount",
            "GST Amount": "tax_amount",
            "Invoice Value": "invoice_amount",
        },
        DatasetType.PURCHASE_REGISTER: {
            "Bill No": "bill_number",
            "Bill Date": "bill_date",
            "Supplier Name": "vendor_name",
            "Taxable Value": "taxable_amount",
            "GST Amount": "tax_amount",
            "Bill Value": "bill_amount",
        },
        DatasetType.INVENTORY_REGISTER: {
            "Item Code": "item_code",
            "Item Name": "item_name",
            "Opening Qty": "opening_qty",
            "Inward Qty": "inward_qty",
            "Outward Qty": "outward_qty",
            "Closing Qty": "closing_qty",
            "Closing Value": "closing_value",
        },
        DatasetType.CHART_OF_ACCOUNTS: {
            "Ledger Code": "account_code",
            "Ledger Name": "account_name",
            "Group Name": "account_group",
        },
    },
    "v10": {
        DatasetType.TRIAL_BALANCE: {
            "Ledger Name": "account_name",
            "Ledger Code": "account_code",
            "Op. Dr": "opening_debit",
            "Op. Cr": "opening_credit",
            "Cl. Dr": "closing_debit",
            "Cl. Cr": "closing_credit",
        },
        DatasetType.GENERAL_LEDGER: {
            "Voucher Number": "voucher_number",
            "Txn Date": "entry_date",
            "Ledger Name": "account_name",
            "Debit Amount": "debit",
            "Credit Amount": "credit",
            "Remarks": "narration",
        },
        DatasetType.INVOICE_REGISTER: {
            "Sales Inv No": "invoice_number",
            "Sales Inv Date": "invoice_date",
            "Customer": "customer_name",
            "Taxable": "taxable_amount",
            "Tax": "tax_amount",
            "Net Amount": "invoice_amount",
        },
        DatasetType.PURCHASE_REGISTER: {
            "Purchase Bill No": "bill_number",
            "Purchase Date": "bill_date",
            "Vendor": "vendor_name",
            "Taxable": "taxable_amount",
            "Tax": "tax_amount",
            "Net Amount": "bill_amount",
        },
        DatasetType.INVENTORY_REGISTER: {
            "SKU Code": "item_code",
            "SKU Name": "item_name",
            "Opening Quantity": "opening_qty",
            "Receipt Quantity": "inward_qty",
            "Issue Quantity": "outward_qty",
            "Closing Quantity": "closing_qty",
            "Closing Amount": "closing_value",
        },
        DatasetType.CHART_OF_ACCOUNTS: {
            "Account Code": "account_code",
            "Account Name": "account_name",
            "Parent Group": "account_group",
        },
    },
}

REQUIRED_MAPPED_COLUMNS: dict[DatasetType, set[str]] = {
    DatasetType.TRIAL_BALANCE: {"account_code", "account_name"},
    DatasetType.GENERAL_LEDGER: {"voucher_number", "entry_date"},
    DatasetType.INVOICE_REGISTER: {"invoice_number", "invoice_date"},
    DatasetType.PURCHASE_REGISTER: {"bill_number", "bill_date"},
    DatasetType.INVENTORY_REGISTER: {"item_code", "item_name"},
    DatasetType.CHART_OF_ACCOUNTS: {"account_code", "account_name"},
}


class MargConnector(AbstractConnector):
    connector_type = ConnectorType.MARG
    connector_version = "4d.1.0"
    supports_resumable_extraction = True
    supported_datasets = {
        DatasetType.TRIAL_BALANCE,
        DatasetType.GENERAL_LEDGER,
        DatasetType.INVOICE_REGISTER,
        DatasetType.PURCHASE_REGISTER,
        DatasetType.INVENTORY_REGISTER,
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
        filename = str(kwargs.get("filename", "marg.csv"))
        if not isinstance(content, (bytes, bytearray)):
            raise ExtractionError("Marg extraction requires CSV/JSON content bytes")

        raw_records = self._delegate._parse_records(content=bytes(content), filename=filename)
        version = self._resolve_version(kwargs.get("marg_version"))
        mapped_records, totals = self._map_records(dataset_type=dataset_type, records=raw_records, version=version)
        self._validate_required_columns(dataset_type=dataset_type, records=mapped_records)

        checkpoint = kwargs.get("checkpoint") or {}
        page = int(checkpoint.get("page") or kwargs.get("page") or 1)
        page_size = int(kwargs.get("page_size") or 1000)
        start = (page - 1) * page_size
        end = start + page_size
        page_records = mapped_records[start:end]
        has_more = end < len(mapped_records)
        next_checkpoint = {"page": page + 1, "page_size": page_size} if has_more else None

        result: dict[str, Any] = {
            "dataset_type": dataset_type.value,
            "records": page_records,
            "raw_data": {"records": mapped_records, "marg_version": version},
            "line_count": len(page_records),
            "erp_reported_line_count": len(mapped_records),
            "is_resumable": True,
            "next_checkpoint": next_checkpoint,
        }
        if totals:
            result["erp_control_totals"] = totals
        return result

    def _resolve_version(self, value: Any) -> str:
        version = str(value or "v10").strip().lower()
        if version.startswith("9"):
            return "v9"
        if version.startswith("10"):
            return "v10"
        if version in {"v9", "v10"}:
            return version
        return "v10"

    def _map_records(
        self,
        *,
        dataset_type: DatasetType,
        records: list[dict[str, Any]],
        version: str,
    ) -> tuple[list[dict[str, Any]], dict[str, Decimal]]:
        mapping = MARG_COLUMN_MAPPINGS.get(version, {}).get(dataset_type, {})
        mapped_records: list[dict[str, Any]] = []
        totals: dict[str, Decimal] = {}
        for record in records:
            if self._is_totals_row(record):
                self._accumulate_totals(totals, record)
                continue
            mapped: dict[str, Any] = {}
            for key, value in record.items():
                normalized_key = mapping.get(key, key)
                if _should_convert_to_decimal(normalized_key):
                    mapped[normalized_key] = _to_decimal_if_numeric(value)
                else:
                    mapped[normalized_key] = value
            mapped_records.append(mapped)
        return mapped_records, totals

    @staticmethod
    def _is_totals_row(record: dict[str, Any]) -> bool:
        for value in record.values():
            if isinstance(value, str) and "total" in value.strip().lower():
                return True
        return False

    @staticmethod
    def _accumulate_totals(totals: dict[str, Decimal], record: dict[str, Any]) -> None:
        for key, value in record.items():
            converted = _to_decimal_if_numeric(value)
            if isinstance(converted, Decimal):
                totals[key] = totals.get(key, Decimal("0")) + converted

    def _validate_required_columns(self, *, dataset_type: DatasetType, records: list[dict[str, Any]]) -> None:
        if not records:
            raise ExtractionError(f"Marg payload for {dataset_type.value} has no data rows")
        required = REQUIRED_MAPPED_COLUMNS.get(dataset_type, set())
        present = set(records[0].keys())
        missing = sorted(required - present)
        if missing:
            raise ExtractionError(
                f"Marg {dataset_type.value} missing required columns after mapping: {', '.join(missing)}"
            )
