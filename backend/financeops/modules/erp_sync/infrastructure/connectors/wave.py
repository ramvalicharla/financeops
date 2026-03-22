from __future__ import annotations

import asyncio
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


class WaveConnector(AbstractConnector):
    connector_type = ConnectorType.WAVE
    connector_version = "4e.1.0"
    supports_resumable_extraction = True
    supported_datasets = {
        DatasetType.TRIAL_BALANCE,
        DatasetType.PROFIT_AND_LOSS,
        DatasetType.BALANCE_SHEET,
        DatasetType.INVOICE_REGISTER,
        DatasetType.ACCOUNTS_RECEIVABLE,
        DatasetType.CHART_OF_ACCOUNTS,
        DatasetType.CUSTOMER_MASTER,
    }

    _GRAPHQL_QUERY_BY_DATASET: dict[DatasetType, str] = {
        DatasetType.TRIAL_BALANCE: "query TrialBalance($after: String) { business { trialBalance(first: 100, after: $after) { pageInfo { hasNextPage endCursor } edges { node { accountName debit credit balance } } } } }",
        DatasetType.PROFIT_AND_LOSS: "query ProfitAndLoss($after: String) { business { profitAndLoss(first: 100, after: $after) { pageInfo { hasNextPage endCursor } edges { node { accountName income expense net } } } } }",
        DatasetType.BALANCE_SHEET: "query BalanceSheet($after: String) { business { balanceSheet(first: 100, after: $after) { pageInfo { hasNextPage endCursor } edges { node { accountName amount section } } } } }",
        DatasetType.INVOICE_REGISTER: "query Invoices($after: String) { business { invoices(first: 100, after: $after) { pageInfo { hasNextPage endCursor } edges { node { id invoiceNumber customerName total status dueDate } } } } }",
        DatasetType.ACCOUNTS_RECEIVABLE: "query Receivables($after: String) { business { accountsReceivable(first: 100, after: $after) { pageInfo { hasNextPage endCursor } edges { node { customerName invoiceNumber amountDue dueDate ageingBucket } } } } }",
        DatasetType.CHART_OF_ACCOUNTS: "query Accounts($after: String) { business { accounts(first: 100, after: $after) { pageInfo { hasNextPage endCursor } edges { node { id name code type } } } } }",
        DatasetType.CUSTOMER_MASTER: "query Customers($after: String) { business { customers(first: 100, after: $after) { pageInfo { hasNextPage endCursor } edges { node { id name email phone status } } } } }",
    }

    def __init__(self, *, secret_store: SecretStore | None = None) -> None:
        self._secret_store = secret_store or SecretStore()

    async def test_connection(self, credentials: dict[str, Any]) -> dict[str, Any]:
        resolved = await self._resolve_credentials(credentials=credentials)
        token = await self._resolve_access_token(resolved)
        payload = await self._graphql_request(
            resolved,
            access_token=token,
            query="query Viewer { business { id name } }",
            variables={},
        )
        return {
            "ok": True,
            "connector_type": self.connector_type.value,
            "business": payload.get("data", {}).get("business"),
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
        token = await self._resolve_access_token(resolved)
        checkpoint = kwargs.get("checkpoint") or {}
        after_cursor = checkpoint.get("after_cursor") or kwargs.get("after_cursor")
        query = self._GRAPHQL_QUERY_BY_DATASET[dataset_type]
        payload = await self._graphql_request(
            resolved,
            access_token=token,
            query=query,
            variables={"after": after_cursor},
        )
        normalized = _normalize_payload(payload)
        records, page_info = self._extract_records(normalized)
        next_checkpoint = (
            {"after_cursor": page_info.get("endCursor")}
            if bool(page_info.get("hasNextPage")) and page_info.get("endCursor")
            else None
        )
        return {
            "dataset_type": dataset_type.value,
            "raw_data": normalized,
            "records": records,
            "line_count": len(records),
            "erp_reported_line_count": len(records),
            "is_resumable": True,
            "next_checkpoint": next_checkpoint,
        }

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
            for key in ("client_id", "client_secret", "access_token", "refresh_token", "base_url"):
                if key in extra and extra[key] is not None:
                    resolved[key] = extra[key]
        resolved.setdefault("base_url", "https://gql.waveapps.com/graphql/public")
        for key in ("client_id", "client_secret"):
            if not resolved.get(key):
                raise ExtractionError(f"Wave credential {key} is required")
        return resolved

    async def _resolve_access_token(self, credentials: dict[str, Any]) -> str:
        access_token = credentials.get("access_token")
        if access_token:
            return str(access_token)
        refresh_token = credentials.get("refresh_token")
        if not refresh_token:
            raise ExtractionError("Wave access_token or refresh_token is required")
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(
                "https://api.waveapps.com/oauth/token",
                json={
                    "grant_type": "refresh_token",
                    "refresh_token": str(refresh_token),
                    "client_id": str(credentials["client_id"]),
                    "client_secret": str(credentials["client_secret"]),
                },
                headers={"Accept": "application/json"},
            )
        if response.status_code >= 400:
            raise ExtractionError(f"Wave token refresh failed ({response.status_code})")
        payload = response.json()
        token = payload.get("access_token")
        if not token:
            raise ExtractionError("Wave token response missing access_token")
        return str(token)

    async def _graphql_request(
        self,
        credentials: dict[str, Any],
        *,
        access_token: str,
        query: str,
        variables: dict[str, Any],
    ) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
        max_attempts = 4
        async with httpx.AsyncClient(timeout=45.0) as client:
            for attempt in range(max_attempts):
                response = await client.post(
                    str(credentials["base_url"]),
                    json={"query": query, "variables": variables},
                    headers=headers,
                )
                if response.status_code != 429:
                    break
                if attempt == max_attempts - 1:
                    break
                await asyncio.sleep(2**attempt)
        if response.status_code >= 400:
            raise ExtractionError(f"Wave GraphQL API error {response.status_code}")
        payload = response.json()
        if not isinstance(payload, dict):
            raise ExtractionError("Wave GraphQL returned non-object payload")
        if payload.get("errors"):
            raise ExtractionError("Wave GraphQL returned errors")
        return payload

    @staticmethod
    def _extract_records(payload: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        if not isinstance(payload, dict):
            return [], {}
        data = payload.get("data")
        if not isinstance(data, dict):
            return [], {}
        business = data.get("business")
        if not isinstance(business, dict):
            return [], {}
        for value in business.values():
            if not isinstance(value, dict):
                continue
            edges = value.get("edges")
            if not isinstance(edges, list):
                continue
            records: list[dict[str, Any]] = []
            for edge in edges:
                if isinstance(edge, dict) and isinstance(edge.get("node"), dict):
                    records.append(edge["node"])
            page_info = value.get("pageInfo")
            if isinstance(page_info, dict):
                return records, page_info
            return records, {}
        return [], {}
