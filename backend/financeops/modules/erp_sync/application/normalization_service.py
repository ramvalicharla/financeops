from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, cast, get_args, get_origin

from pydantic import BaseModel

from financeops.core.exceptions import FinanceOpsError
from financeops.modules.erp_sync.domain import canonical
from financeops.modules.erp_sync.domain.canonical.form_26as_ais import (
    CanonicalAISRegister,
    CanonicalForm26AS,
)
from financeops.modules.erp_sync.domain.enums import DatasetType
from financeops.utils.determinism import canonical_json_dumps, sha256_hex_text


class NormalizationNotImplemented(FinanceOpsError):
    status_code = 422
    error_code = "normalization_not_implemented"


class NormalizationService:
    """
    Deterministic normalization from raw connector payload to canonical schemas.
    Unsupported dataset types fail-closed with NormalizationNotImplemented.
    """

    DATASET_MODEL_MAP: dict[DatasetType, type[BaseModel]] = {
        DatasetType.TRIAL_BALANCE: canonical.CanonicalTrialBalance,
        DatasetType.GENERAL_LEDGER: canonical.CanonicalGeneralLedger,
        DatasetType.PROFIT_AND_LOSS: canonical.CanonicalProfitAndLoss,
        DatasetType.BALANCE_SHEET: canonical.CanonicalBalanceSheet,
        DatasetType.CASH_FLOW_STATEMENT: canonical.CanonicalCashFlowStatement,
        DatasetType.ACCOUNTS_RECEIVABLE: canonical.CanonicalAccountsReceivable,
        DatasetType.ACCOUNTS_PAYABLE: canonical.CanonicalAccountsPayable,
        DatasetType.AR_AGEING: canonical.CanonicalAgeingReport,
        DatasetType.AP_AGEING: canonical.CanonicalAgeingReport,
        DatasetType.FIXED_ASSET_REGISTER: canonical.CanonicalFixedAssetRegister,
        DatasetType.PREPAID_REGISTER: canonical.CanonicalPrepaidRegister,
        DatasetType.INVOICE_REGISTER: canonical.CanonicalInvoiceRegister,
        DatasetType.PURCHASE_REGISTER: canonical.CanonicalPurchaseRegister,
        DatasetType.CREDIT_NOTE_REGISTER: canonical.CanonicalInvoiceRegister,
        DatasetType.DEBIT_NOTE_REGISTER: canonical.CanonicalPurchaseRegister,
        DatasetType.SALES_ORDER_REGISTER: canonical.CanonicalSalesOrderRegister,
        DatasetType.PURCHASE_ORDER_REGISTER: canonical.CanonicalPurchaseOrderRegister,
        DatasetType.BANK_STATEMENT: canonical.CanonicalBankTransactions,
        DatasetType.BANK_TRANSACTION_REGISTER: canonical.CanonicalBankTransactions,
        DatasetType.INVENTORY_REGISTER: canonical.CanonicalInventoryRegister,
        DatasetType.INVENTORY_MOVEMENT: canonical.CanonicalInventoryRegister,
        DatasetType.PAYROLL_SUMMARY: canonical.CanonicalPayrollSummary,
        DatasetType.EXPENSE_CLAIMS: canonical.CanonicalExpenseClaims,
        DatasetType.TAX_LEDGER: canonical.CanonicalTaxLedger,
        DatasetType.TDS_REGISTER: canonical.CanonicalTdsRegister,
        DatasetType.GST_RETURN_GSTR1: canonical.CanonicalGstReturn,
        DatasetType.GST_RETURN_GSTR2A: canonical.CanonicalGstReturn,
        DatasetType.GST_RETURN_GSTR2B: canonical.CanonicalGstReturn,
        DatasetType.GST_RETURN_GSTR3B: canonical.CanonicalGstReturn,
        DatasetType.EINVOICE_REGISTER: canonical.CanonicalEinvoiceRegister,
        DatasetType.GST_RETURN_GSTR9: canonical.CanonicalGstr9Stub,
        DatasetType.GST_RETURN_GSTR9C: canonical.CanonicalGstr9cStub,
        DatasetType.FORM_26AS: CanonicalForm26AS,
        DatasetType.AIS_REGISTER: CanonicalAISRegister,
        DatasetType.STAFF_ADVANCES: canonical.CanonicalAdvances,
        DatasetType.VENDOR_ADVANCES: canonical.CanonicalAdvances,
        DatasetType.CUSTOMER_ADVANCES: canonical.CanonicalAdvances,
        DatasetType.INTERCOMPANY_TRANSACTIONS: canonical.CanonicalIntercompanyTransactions,
        DatasetType.BUDGET_DATA: canonical.CanonicalBudgetData,
        DatasetType.PROJECT_LEDGER: canonical.CanonicalProjectLedger,
        DatasetType.CONTRACT_REGISTER: canonical.CanonicalContractRegister,
        DatasetType.OPENING_BALANCES: canonical.CanonicalOpeningBalances,
        DatasetType.SYNC_RECONCILIATION_SUMMARY: canonical.CanonicalSyncReconciliationSummary,
        DatasetType.CHART_OF_ACCOUNTS: canonical.CanonicalMasterData,
        DatasetType.VENDOR_MASTER: canonical.CanonicalMasterData,
        DatasetType.CUSTOMER_MASTER: canonical.CanonicalMasterData,
        DatasetType.DIMENSION_MASTER: canonical.CanonicalMasterData,
        DatasetType.CURRENCY_MASTER: canonical.CanonicalMasterData,
    }

    LIVE_CONNECTOR_DATASETS: frozenset[DatasetType] = frozenset(
        {
            DatasetType.CHART_OF_ACCOUNTS,
            DatasetType.TRIAL_BALANCE,
            DatasetType.GENERAL_LEDGER,
            DatasetType.VENDOR_MASTER,
            DatasetType.CUSTOMER_MASTER,
            DatasetType.DIMENSION_MASTER,
            DatasetType.CURRENCY_MASTER,
            DatasetType.PROFIT_AND_LOSS,
            DatasetType.BALANCE_SHEET,
            DatasetType.CASH_FLOW_STATEMENT,
            DatasetType.INVOICE_REGISTER,
            DatasetType.PURCHASE_REGISTER,
            DatasetType.BANK_TRANSACTION_REGISTER,
            DatasetType.TAX_LEDGER,
            DatasetType.TDS_REGISTER,
            DatasetType.GST_RETURN_GSTR1,
            DatasetType.GST_RETURN_GSTR3B,
            DatasetType.GST_RETURN_GSTR9,
            DatasetType.GST_RETURN_GSTR9C,
            DatasetType.FORM_26AS,
            DatasetType.AIS_REGISTER,
        }
    )

    def normalize(
        self,
        *,
        dataset_type: DatasetType,
        raw_payload: Mapping[str, Any],
        entity_id: str,
        currency: str = "INR",
    ) -> dict[str, Any]:
        model_cls = self.DATASET_MODEL_MAP.get(dataset_type)
        if model_cls is None:
            raise NormalizationNotImplemented(f"No canonical schema registered for {dataset_type.value}")

        if dataset_type not in self.LIVE_CONNECTOR_DATASETS:
            raise NormalizationNotImplemented(
                f"Normalization for {dataset_type.value} is stubbed until connector support is live"
            )

        model_payload = self._build_root_payload(
            model_cls=model_cls,
            dataset_type=dataset_type,
            raw_payload=raw_payload,
            entity_id=entity_id,
            currency=currency,
        )
        model_instance = model_cls(**model_payload)
        output = model_instance.model_dump(mode="python")
        output["dataset_type"] = dataset_type.value
        return output

    def list_normalizer_support(self) -> dict[str, str]:
        support: dict[str, str] = {}
        for dataset_type in DatasetType:
            if dataset_type in self.LIVE_CONNECTOR_DATASETS:
                support[dataset_type.value] = "supported"
            else:
                support[dataset_type.value] = "stub"
        return support

    def _build_root_payload(
        self,
        *,
        model_cls: type[BaseModel],
        dataset_type: DatasetType,
        raw_payload: Mapping[str, Any],
        entity_id: str,
        currency: str,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        now_date = datetime.now(UTC).date()
        records = self._records(raw_payload)
        list_field_name, list_item_model = self._list_field_info(model_cls)

        for field_name, field in model_cls.model_fields.items():
            if field_name == "dataset_token":
                continue
            if field_name == "entity_id":
                payload[field_name] = entity_id
                continue
            if field_name == "currency":
                payload[field_name] = str(raw_payload.get(field_name, currency))
                continue
            if field_name in {"from_date", "to_date", "as_at_date"}:
                payload[field_name] = self._coerce_date(raw_payload.get(field_name), fallback=now_date)
                continue
            if field_name in {"line_count", "erp_reported_line_count"}:
                payload[field_name] = int(raw_payload.get(field_name, len(records)))
                continue

            if list_field_name and field_name == list_field_name and list_item_model is not None:
                payload[field_name] = [
                    self._build_line_payload(list_item_model, record, entity_id=entity_id, currency=currency)
                    for record in records
                ]
                continue

            if field_name == "records":
                payload[field_name] = [
                    self._build_generic_record(record, entity_id=entity_id)
                    for record in records
                ]
                continue

            provided = raw_payload.get(field_name)
            if provided is not None:
                payload[field_name] = provided
                continue
            if field.is_required():
                payload[field_name] = self._fallback_value(field.annotation, field_name, now_date)

        payload["dataset_token"] = self._dataset_token(dataset_type=dataset_type, payload=payload, records=records)
        return payload

    @staticmethod
    def _records(raw_payload: Mapping[str, Any]) -> list[dict[str, Any]]:
        records = raw_payload.get("records", [])
        if not isinstance(records, list):
            return []
        normalized: list[dict[str, Any]] = []
        for item in records:
            if isinstance(item, Mapping):
                normalized.append(dict(item))
        return normalized

    @staticmethod
    def _coerce_date(value: Any, *, fallback: date) -> date:
        if isinstance(value, date):
            return value
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, str):
            try:
                return date.fromisoformat(value)
            except ValueError:
                return fallback
        return fallback

    @staticmethod
    def _list_field_info(model_cls: type[BaseModel]) -> tuple[str | None, type[BaseModel] | None]:
        for candidate in ("lines", "entries", "records"):
            field = model_cls.model_fields.get(candidate)
            if field is None:
                continue
            origin = get_origin(field.annotation)
            args = get_args(field.annotation)
            if origin is list and args and isinstance(args[0], type) and issubclass(args[0], BaseModel):
                return candidate, cast(type[BaseModel], args[0])
        return None, None

    def _build_line_payload(
        self,
        model_cls: type[BaseModel],
        record: Mapping[str, Any],
        *,
        entity_id: str,
        currency: str,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        now_date = datetime.now(UTC).date()
        for field_name, field in model_cls.model_fields.items():
            if field_name == "dataset_token":
                payload[field_name] = None
                continue
            if field_name == "entity_id":
                payload[field_name] = entity_id
                continue
            if field_name == "currency":
                payload[field_name] = str(record.get(field_name, currency))
                continue
            if field_name in {"dimension_refs", "attachment_references"}:
                payload[field_name] = record.get(field_name, {} if field_name == "dimension_refs" else [])
                continue
            value = record.get(field_name)
            if value is None and field.is_required():
                value = self._fallback_value(field.annotation, field_name, now_date)
            elif value is not None:
                value = self._coerce_value(value, field.annotation, field_name, now_date)
            payload[field_name] = value
        return payload

    @staticmethod
    def _build_generic_record(record: Mapping[str, Any], *, entity_id: str) -> dict[str, Any]:
        code = str(record.get("code") or record.get("id") or "unknown")
        name = str(record.get("name") or record.get("label") or code)
        metadata = {
            str(k): str(v)
            for k, v in record.items()
            if k not in {"code", "id", "name", "label"}
        }
        return {
            "code": code,
            "name": name,
            "entity_id": str(record.get("entity_id") or entity_id),
            "metadata": metadata,
        }

    def _fallback_value(self, annotation: Any, field_name: str, fallback_date: date) -> Any:
        origin = get_origin(annotation)
        if annotation is str:
            return f"{field_name}_value"
        if annotation is bool:
            return False
        if annotation is int:
            return 0
        if annotation is Decimal:
            return Decimal("0")
        if annotation is date:
            return fallback_date
        if origin is list:
            return []
        if origin is dict:
            return {}
        if origin is not None and type(None) in get_args(annotation):
            return None
        return None

    def _coerce_value(self, value: Any, annotation: Any, field_name: str, fallback_date: date) -> Any:
        if annotation is Decimal:
            try:
                return Decimal(str(value))
            except (InvalidOperation, ValueError, TypeError):
                return Decimal("0")
        if annotation is date:
            return self._coerce_date(value, fallback=fallback_date)
        if annotation is bool:
            return bool(value)
        if annotation is int:
            try:
                return int(value)
            except (ValueError, TypeError):
                return 0
        if annotation is str:
            return str(value)
        origin = get_origin(annotation)
        if origin is list and not isinstance(value, list):
            return [value]
        if origin is dict and not isinstance(value, dict):
            return {}
        return value

    @staticmethod
    def _dataset_token(*, dataset_type: DatasetType, payload: Mapping[str, Any], records: list[dict[str, Any]]) -> str:
        token_payload = {
            "dataset_type": dataset_type.value,
            "payload": NormalizationService._json_safe(payload),
            "records": NormalizationService._json_safe(records),
        }
        return sha256_hex_text(canonical_json_dumps(token_payload))

    @staticmethod
    def _json_safe(value: Any) -> Any:
        if isinstance(value, Mapping):
            return {str(k): NormalizationService._json_safe(v) for k, v in value.items()}
        if isinstance(value, list):
            return [NormalizationService._json_safe(item) for item in value]
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        return value

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        dataset_type = kwargs.get("dataset_type")
        if isinstance(dataset_type, str):
            dataset_type = DatasetType(dataset_type)
        if not isinstance(dataset_type, DatasetType):
            raise ValueError("dataset_type is required")
        raw_payload = kwargs.get("raw_payload", {})
        if not isinstance(raw_payload, Mapping):
            raise ValueError("raw_payload must be a mapping")
        entity_id = str(kwargs.get("entity_id", "entity_undefined"))
        currency = str(kwargs.get("currency", "INR"))
        return self.normalize(
            dataset_type=dataset_type,
            raw_payload=raw_payload,
            entity_id=entity_id,
            currency=currency,
        )
