from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import Any

from financeops.core.exceptions import FinanceOpsError
from financeops.modules.erp_sync.domain.enums import ConnectorType, DatasetType


class ConnectorCapabilityNotSupported(FinanceOpsError):
    status_code = 422
    error_code = "connector_capability_not_supported"

    def __init__(self, connector_type: ConnectorType, dataset_type: DatasetType) -> None:
        super().__init__(f"Connector {connector_type.value} does not support {dataset_type.value}")


class ExtractionError(FinanceOpsError):
    status_code = 502
    error_code = "extraction_error"


class AbstractConnector(ABC):
    connector_type: ConnectorType
    connector_version: str = "1.0.0"
    supported_datasets: set[DatasetType] = set()
    supports_resumable_extraction: bool = False

    def _unsupported(self, dataset_type: DatasetType) -> None:
        raise ConnectorCapabilityNotSupported(self.connector_type, dataset_type)

    @abstractmethod
    async def test_connection(self, credentials: dict[str, Any]) -> dict[str, Any]:
        """
        Test connectivity to the ERP system.
        Returns {"ok": True, "latency_ms": int} on success.
        Returns {"ok": False, "error": str} on failure.
        Raises ConnectorAuthError if credentials are invalid.
        """
        ...

    async def extract(self, dataset_type: DatasetType, **kwargs: Any) -> dict[str, Any]:
        method_name = f"extract_{dataset_type.value}"
        method = getattr(self, method_name, None)
        if method is None:
            self._unsupported(dataset_type)
        return await method(**kwargs)

    async def extract_trial_balance(self, **kwargs: Any) -> dict[str, Any]:
        self._unsupported(DatasetType.TRIAL_BALANCE)

    async def extract_general_ledger(self, **kwargs: Any) -> dict[str, Any]:
        self._unsupported(DatasetType.GENERAL_LEDGER)

    async def extract_profit_and_loss(self, **kwargs: Any) -> dict[str, Any]:
        self._unsupported(DatasetType.PROFIT_AND_LOSS)

    async def extract_balance_sheet(self, **kwargs: Any) -> dict[str, Any]:
        self._unsupported(DatasetType.BALANCE_SHEET)

    async def extract_cash_flow_statement(self, **kwargs: Any) -> dict[str, Any]:
        self._unsupported(DatasetType.CASH_FLOW_STATEMENT)

    async def extract_accounts_receivable(self, **kwargs: Any) -> dict[str, Any]:
        self._unsupported(DatasetType.ACCOUNTS_RECEIVABLE)

    async def extract_accounts_payable(self, **kwargs: Any) -> dict[str, Any]:
        self._unsupported(DatasetType.ACCOUNTS_PAYABLE)

    async def extract_ar_ageing(self, **kwargs: Any) -> dict[str, Any]:
        self._unsupported(DatasetType.AR_AGEING)

    async def extract_ap_ageing(self, **kwargs: Any) -> dict[str, Any]:
        self._unsupported(DatasetType.AP_AGEING)

    async def extract_fixed_asset_register(self, **kwargs: Any) -> dict[str, Any]:
        self._unsupported(DatasetType.FIXED_ASSET_REGISTER)

    async def extract_prepaid_register(self, **kwargs: Any) -> dict[str, Any]:
        self._unsupported(DatasetType.PREPAID_REGISTER)

    async def extract_invoice_register(self, **kwargs: Any) -> dict[str, Any]:
        self._unsupported(DatasetType.INVOICE_REGISTER)

    async def extract_purchase_register(self, **kwargs: Any) -> dict[str, Any]:
        self._unsupported(DatasetType.PURCHASE_REGISTER)

    async def extract_credit_note_register(self, **kwargs: Any) -> dict[str, Any]:
        self._unsupported(DatasetType.CREDIT_NOTE_REGISTER)

    async def extract_debit_note_register(self, **kwargs: Any) -> dict[str, Any]:
        self._unsupported(DatasetType.DEBIT_NOTE_REGISTER)

    async def extract_sales_order_register(self, **kwargs: Any) -> dict[str, Any]:
        self._unsupported(DatasetType.SALES_ORDER_REGISTER)

    async def extract_purchase_order_register(self, **kwargs: Any) -> dict[str, Any]:
        self._unsupported(DatasetType.PURCHASE_ORDER_REGISTER)

    async def extract_bank_statement(self, **kwargs: Any) -> dict[str, Any]:
        self._unsupported(DatasetType.BANK_STATEMENT)

    async def extract_bank_transaction_register(self, **kwargs: Any) -> dict[str, Any]:
        self._unsupported(DatasetType.BANK_TRANSACTION_REGISTER)

    async def extract_inventory_register(self, **kwargs: Any) -> dict[str, Any]:
        self._unsupported(DatasetType.INVENTORY_REGISTER)

    async def extract_inventory_movement(self, **kwargs: Any) -> dict[str, Any]:
        self._unsupported(DatasetType.INVENTORY_MOVEMENT)

    async def extract_payroll_summary(self, **kwargs: Any) -> dict[str, Any]:
        self._unsupported(DatasetType.PAYROLL_SUMMARY)

    async def extract_expense_claims(self, **kwargs: Any) -> dict[str, Any]:
        self._unsupported(DatasetType.EXPENSE_CLAIMS)

    async def extract_tax_ledger(self, **kwargs: Any) -> dict[str, Any]:
        self._unsupported(DatasetType.TAX_LEDGER)

    async def extract_tds_register(self, **kwargs: Any) -> dict[str, Any]:
        self._unsupported(DatasetType.TDS_REGISTER)

    async def extract_gst_return_gstr1(self, **kwargs: Any) -> dict[str, Any]:
        self._unsupported(DatasetType.GST_RETURN_GSTR1)

    async def extract_gst_return_gstr2a(self, **kwargs: Any) -> dict[str, Any]:
        self._unsupported(DatasetType.GST_RETURN_GSTR2A)

    async def extract_gst_return_gstr2b(self, **kwargs: Any) -> dict[str, Any]:
        self._unsupported(DatasetType.GST_RETURN_GSTR2B)

    async def extract_gst_return_gstr3b(self, **kwargs: Any) -> dict[str, Any]:
        self._unsupported(DatasetType.GST_RETURN_GSTR3B)

    async def extract_einvoice_register(self, **kwargs: Any) -> dict[str, Any]:
        self._unsupported(DatasetType.EINVOICE_REGISTER)

    async def extract_gst_return_gstr9(self, **kwargs: Any) -> dict[str, Any]:
        self._unsupported(DatasetType.GST_RETURN_GSTR9)

    async def extract_gst_return_gstr9c(self, **kwargs: Any) -> dict[str, Any]:
        self._unsupported(DatasetType.GST_RETURN_GSTR9C)

    async def extract_form_26as(self, **kwargs: Any) -> dict[str, Any]:
        self._unsupported(DatasetType.FORM_26AS)

    async def extract_ais_register(self, **kwargs: Any) -> dict[str, Any]:
        self._unsupported(DatasetType.AIS_REGISTER)

    async def extract_staff_advances(self, **kwargs: Any) -> dict[str, Any]:
        self._unsupported(DatasetType.STAFF_ADVANCES)

    async def extract_vendor_advances(self, **kwargs: Any) -> dict[str, Any]:
        self._unsupported(DatasetType.VENDOR_ADVANCES)

    async def extract_customer_advances(self, **kwargs: Any) -> dict[str, Any]:
        self._unsupported(DatasetType.CUSTOMER_ADVANCES)

    async def extract_intercompany_transactions(self, **kwargs: Any) -> dict[str, Any]:
        self._unsupported(DatasetType.INTERCOMPANY_TRANSACTIONS)

    async def extract_budget_data(self, **kwargs: Any) -> dict[str, Any]:
        self._unsupported(DatasetType.BUDGET_DATA)

    async def extract_project_ledger(self, **kwargs: Any) -> dict[str, Any]:
        self._unsupported(DatasetType.PROJECT_LEDGER)

    async def extract_contract_register(self, **kwargs: Any) -> dict[str, Any]:
        self._unsupported(DatasetType.CONTRACT_REGISTER)

    async def extract_opening_balances(self, **kwargs: Any) -> dict[str, Any]:
        self._unsupported(DatasetType.OPENING_BALANCES)

    async def extract_sync_reconciliation_summary(self, **kwargs: Any) -> dict[str, Any]:
        self._unsupported(DatasetType.SYNC_RECONCILIATION_SUMMARY)

    async def extract_chart_of_accounts(self, **kwargs: Any) -> dict[str, Any]:
        self._unsupported(DatasetType.CHART_OF_ACCOUNTS)

    async def extract_vendor_master(self, **kwargs: Any) -> dict[str, Any]:
        self._unsupported(DatasetType.VENDOR_MASTER)

    async def extract_customer_master(self, **kwargs: Any) -> dict[str, Any]:
        self._unsupported(DatasetType.CUSTOMER_MASTER)

    async def extract_dimension_master(self, **kwargs: Any) -> dict[str, Any]:
        self._unsupported(DatasetType.DIMENSION_MASTER)

    async def extract_currency_master(self, **kwargs: Any) -> dict[str, Any]:
        self._unsupported(DatasetType.CURRENCY_MASTER)

    async def resolve_period(self, *, period_start: date | None, period_end: date | None) -> dict[str, Any]:
        return {
            "period_start": period_start.isoformat() if period_start else None,
            "period_end": period_end.isoformat() if period_end else None,
        }
