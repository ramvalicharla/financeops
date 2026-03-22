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


_ZERO_DECIMAL_CURRENCIES = {"bif", "clp", "djf", "gnf", "jpy", "kmf", "krw", "mga", "pyg", "rwf", "vnd", "vuv", "xaf", "xof", "xpf"}


def _to_decimal(value: Any) -> Decimal | None:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, str):
        cleaned = value.strip().replace(",", "")
        if cleaned and all(ch.isdigit() or ch in {"-", "."} for ch in cleaned):
            try:
                return Decimal(cleaned)
            except (InvalidOperation, ValueError):
                return None
    return None


def _amount_to_currency_units(amount_value: Any, currency: str | None) -> Any:
    amount = _to_decimal(amount_value)
    if amount is None:
        return amount_value
    curr = (currency or "").lower()
    divisor = Decimal("1") if curr in _ZERO_DECIMAL_CURRENCIES else Decimal("100")
    return (amount / divisor).quantize(Decimal("0.01")) if divisor != Decimal("1") else amount


def _normalize_payload(value: Any, *, currency: str | None = None, parent_key: str | None = None) -> Any:
    if isinstance(value, dict):
        current_currency = str(value.get("currency", currency) or "").lower() or currency
        normalized: dict[str, Any] = {}
        for key, item in value.items():
            normalized[key] = _normalize_payload(item, currency=current_currency, parent_key=key.lower())
        return normalized
    if isinstance(value, list):
        return [_normalize_payload(item, currency=currency, parent_key=parent_key) for item in value]
    if parent_key and "amount" in parent_key:
        return _amount_to_currency_units(value, currency)
    return value


class StripeConnector(AbstractConnector):
    connector_type = ConnectorType.STRIPE
    connector_version = "4e.1.0"
    supports_resumable_extraction = True
    supported_datasets = {
        DatasetType.BANK_STATEMENT,
        DatasetType.BANK_TRANSACTION_REGISTER,
        DatasetType.INVOICE_REGISTER,
        DatasetType.ACCOUNTS_RECEIVABLE,
    }

    _DATASET_ENDPOINTS: dict[DatasetType, str] = {
        DatasetType.BANK_STATEMENT: "payouts",
        DatasetType.BANK_TRANSACTION_REGISTER: "balance_transactions",
        DatasetType.INVOICE_REGISTER: "invoices",
        DatasetType.ACCOUNTS_RECEIVABLE: "charges",
    }

    def __init__(self, *, secret_store: SecretStore | None = None) -> None:
        self._secret_store = secret_store or SecretStore()

    async def test_connection(self, credentials: dict[str, Any]) -> dict[str, Any]:
        resolved = await self._resolve_credentials(credentials=credentials)
        payload = await self._request_json(
            resolved,
            endpoint="balance",
            params={},
        )
        return {"ok": True, "connector_type": self.connector_type.value, "payload": payload}

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
        checkpoint = kwargs.get("checkpoint") or {}
        limit = int(checkpoint.get("limit") or kwargs.get("limit") or 100)
        starting_after = checkpoint.get("starting_after") or kwargs.get("starting_after")
        params: dict[str, Any] = {"limit": limit}
        if starting_after:
            params["starting_after"] = str(starting_after)
        endpoint = self._DATASET_ENDPOINTS[dataset_type]
        payload = await self._request_json(resolved, endpoint=endpoint, params=params)
        normalized = _normalize_payload(payload)
        records = self._extract_records(normalized)
        has_more = bool(payload.get("has_more")) if isinstance(payload, dict) else False
        next_checkpoint = None
        if has_more and records:
            last_id = records[-1].get("id")
            if last_id:
                next_checkpoint = {"starting_after": str(last_id), "limit": limit}
        result: dict[str, Any] = {
            "dataset_type": dataset_type.value,
            "raw_data": normalized,
            "records": records,
            "line_count": len(records),
            "erp_reported_line_count": len(records),
            "is_resumable": True,
            "next_checkpoint": next_checkpoint,
        }
        if dataset_type == DatasetType.BANK_STATEMENT:
            result["erp_control_totals"] = self._compute_payout_totals(records)
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
            for key in ("secret_key", "base_url"):
                if key in extra and extra[key] is not None:
                    resolved[key] = extra[key]
        resolved.setdefault("base_url", "https://api.stripe.com/v1")
        if not resolved.get("secret_key"):
            raise ExtractionError("Stripe secret_key is required")
        return resolved

    async def _request_json(
        self,
        credentials: dict[str, Any],
        *,
        endpoint: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        url = f"{str(credentials['base_url']).rstrip('/')}/{endpoint.lstrip('/')}"
        headers = {"Authorization": f"Bearer {credentials['secret_key']}", "Accept": "application/json"}
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.get(url, headers=headers, params=params)
        if response.status_code >= 400:
            raise ExtractionError(f"Stripe API error {response.status_code} for {endpoint}")
        payload = response.json()
        if not isinstance(payload, dict):
            raise ExtractionError("Stripe API returned non-object payload")
        return payload

    @staticmethod
    def _extract_records(payload: Any) -> list[dict[str, Any]]:
        if not isinstance(payload, dict):
            return []
        data = payload.get("data")
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        for key in ("items", "records"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        return []

    @staticmethod
    def _compute_payout_totals(records: list[dict[str, Any]]) -> dict[str, Decimal]:
        total = Decimal("0")
        for row in records:
            amount = row.get("amount")
            if isinstance(amount, Decimal):
                total += amount
        return {"total_payout_amount": total}
