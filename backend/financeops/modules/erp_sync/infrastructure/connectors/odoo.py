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


class OdooConnector(AbstractConnector):
    connector_type = ConnectorType.ODOO
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
        DatasetType.INVENTORY_REGISTER,
        DatasetType.CHART_OF_ACCOUNTS,
        DatasetType.VENDOR_MASTER,
        DatasetType.CUSTOMER_MASTER,
    }

    _DATASET_MODEL_MAP: dict[DatasetType, tuple[str, list[str]]] = {
        DatasetType.TRIAL_BALANCE: ("account.move.line", ["account_id", "debit", "credit", "balance", "date"]),
        DatasetType.GENERAL_LEDGER: ("account.move.line", ["move_id", "account_id", "debit", "credit", "date", "name"]),
        DatasetType.PROFIT_AND_LOSS: ("account.move.line", ["account_id", "debit", "credit", "balance", "date"]),
        DatasetType.BALANCE_SHEET: ("account.move.line", ["account_id", "debit", "credit", "balance", "date"]),
        DatasetType.ACCOUNTS_RECEIVABLE: ("account.move.line", ["partner_id", "amount_residual", "date", "move_id"]),
        DatasetType.ACCOUNTS_PAYABLE: ("account.move.line", ["partner_id", "amount_residual", "date", "move_id"]),
        DatasetType.INVOICE_REGISTER: ("account.move", ["name", "invoice_date", "invoice_date_due", "amount_total", "partner_id"]),
        DatasetType.PURCHASE_REGISTER: ("account.move", ["name", "invoice_date", "invoice_date_due", "amount_total", "partner_id"]),
        DatasetType.INVENTORY_REGISTER: ("stock.move", ["date", "product_id", "product_uom_qty", "value", "reference"]),
        DatasetType.CHART_OF_ACCOUNTS: ("account.account", ["code", "name", "account_type"]),
        DatasetType.VENDOR_MASTER: ("res.partner", ["name", "email", "phone", "supplier_rank"]),
        DatasetType.CUSTOMER_MASTER: ("res.partner", ["name", "email", "phone", "customer_rank"]),
    }

    def __init__(self, *, secret_store: SecretStore | None = None) -> None:
        self._secret_store = secret_store or SecretStore()

    async def test_connection(self, credentials: dict[str, Any]) -> dict[str, Any]:
        resolved = await self._resolve_credentials(credentials=credentials)
        uid = await self._authenticate(resolved)
        return {
            "ok": True,
            "connector_type": self.connector_type.value,
            "database": resolved["database"],
            "uid": uid,
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
        uid = await self._authenticate(resolved)
        checkpoint = kwargs.get("checkpoint") or {}
        offset = int(checkpoint.get("offset") or kwargs.get("offset") or 0)
        limit = int(checkpoint.get("page_size") or kwargs.get("page_size") or 1000)
        model, fields = self._DATASET_MODEL_MAP[dataset_type]
        domain = self._build_domain(dataset_type)
        payload = await self._call_kw(
            resolved,
            model=model,
            method="search_read",
            args=[domain],
            kwargs={"fields": fields, "limit": limit, "offset": offset, "order": "id asc"},
            uid=uid,
        )
        normalized = _normalize_payload(payload)
        records = [row for row in normalized if isinstance(row, dict)] if isinstance(normalized, list) else []
        next_checkpoint = {"offset": offset + limit, "page_size": limit} if len(records) >= limit else None
        result: dict[str, Any] = {
            "dataset_type": dataset_type.value,
            "raw_data": {"rows": normalized, "odoo_version": resolved.get("odoo_version", "unknown")},
            "records": records,
            "line_count": len(records),
            "erp_reported_line_count": len(records),
            "is_resumable": True,
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
            for key in ("url", "database", "username", "api_key", "password", "odoo_version"):
                if key in extra and extra[key] is not None:
                    resolved[key] = extra[key]
        for key in ("url", "database", "username"):
            if not resolved.get(key):
                raise ExtractionError(f"Odoo credential {key} is required")
        if not resolved.get("api_key") and not resolved.get("password"):
            raise ExtractionError("Odoo api_key or password is required")
        return resolved

    async def _authenticate(self, credentials: dict[str, Any]) -> int:
        payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
                "db": credentials["database"],
                "login": credentials["username"],
                "password": credentials.get("api_key") or credentials.get("password"),
            },
            "id": 1,
        }
        url = f"{str(credentials['url']).rstrip('/')}/web/session/authenticate"
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(url, json=payload, headers={"Content-Type": "application/json"})
        if response.status_code >= 400:
            raise ExtractionError(f"Odoo authentication failed ({response.status_code})")
        body = response.json()
        result = body.get("result", {}) if isinstance(body, dict) else {}
        uid = result.get("uid")
        if not isinstance(uid, int):
            raise ExtractionError("Odoo authentication response missing uid")
        return uid

    async def _call_kw(
        self,
        credentials: dict[str, Any],
        *,
        model: str,
        method: str,
        args: list[Any],
        kwargs: dict[str, Any],
        uid: int,
    ) -> Any:
        payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
                "model": model,
                "method": method,
                "args": args,
                "kwargs": kwargs,
                "db": credentials["database"],
                "uid": uid,
                "password": credentials.get("api_key") or credentials.get("password"),
            },
            "id": 2,
        }
        url = f"{str(credentials['url']).rstrip('/')}/web/dataset/call_kw"
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(url, json=payload, headers={"Content-Type": "application/json"})
        if response.status_code >= 400:
            raise ExtractionError(f"Odoo call_kw failed ({response.status_code})")
        body = response.json()
        if not isinstance(body, dict):
            raise ExtractionError("Odoo call_kw returned non-object payload")
        if body.get("error"):
            raise ExtractionError("Odoo call_kw returned error payload")
        return body.get("result", [])

    @staticmethod
    def _build_domain(dataset_type: DatasetType) -> list[Any]:
        if dataset_type == DatasetType.VENDOR_MASTER:
            return [["supplier_rank", ">", 0]]
        if dataset_type == DatasetType.CUSTOMER_MASTER:
            return [["customer_rank", ">", 0]]
        return []

    @staticmethod
    def _extract_control_totals(records: list[dict[str, Any]]) -> dict[str, Decimal]:
        totals = {"total_debit": Decimal("0"), "total_credit": Decimal("0"), "total_balance": Decimal("0")}
        for row in records:
            debit = row.get("debit")
            credit = row.get("credit")
            balance = row.get("balance")
            if isinstance(debit, Decimal):
                totals["total_debit"] += debit
            if isinstance(credit, Decimal):
                totals["total_credit"] += credit
            if isinstance(balance, Decimal):
                totals["total_balance"] += balance
        return totals
