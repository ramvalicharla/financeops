from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

import httpx

from financeops.modules.erp_sync.domain.enums import ConnectorType, DatasetType
from financeops.modules.erp_sync.infrastructure.connectors.base import AbstractConnector, ExtractionError


class AuthenticationError(ExtractionError):
    """Zoho authentication/token lifecycle failure."""


class ZohoConnector(AbstractConnector):
    connector_type = ConnectorType.ZOHO
    connector_version = "1.1.0"
    supports_resumable_extraction = True
    supported_datasets = {
        DatasetType.TRIAL_BALANCE,
        DatasetType.GENERAL_LEDGER,
        DatasetType.PROFIT_AND_LOSS,
        DatasetType.BALANCE_SHEET,
        DatasetType.CASH_FLOW_STATEMENT,
        DatasetType.INVOICE_REGISTER,
        DatasetType.PURCHASE_REGISTER,
        DatasetType.CUSTOMER_MASTER,
        DatasetType.VENDOR_MASTER,
        DatasetType.CHART_OF_ACCOUNTS,
        DatasetType.BANK_TRANSACTION_REGISTER,
        DatasetType.TAX_LEDGER,
        DatasetType.TDS_REGISTER,
        DatasetType.GST_RETURN_GSTR1,
        DatasetType.GST_RETURN_GSTR3B,
    }

    ZOHO_TOKEN_URL = "https://accounts.zoho.in/oauth/v2/token"
    ZOHO_API_BASE = "https://books.zoho.in/api/v3"

    async def _fetch(self, endpoint: str, *, access_token: str, base_url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        headers = {"Authorization": f"Zoho-oauthtoken {access_token}"}
        url = f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers, params=params or {})
        if response.status_code in {401, 403}:
            raise AuthenticationError(f"Zoho API auth error ({response.status_code}) for {endpoint}")
        if response.status_code >= 400:
            raise ExtractionError(f"Zoho API error ({response.status_code}) for {endpoint}")
        payload = response.json()
        if not isinstance(payload, dict):
            raise ExtractionError("Unexpected Zoho payload format")
        return payload

    def _token_is_expired(self, creds: dict[str, Any]) -> bool:
        token_expiry = creds.get("token_expires_at")
        if token_expiry is None:
            return True
        if isinstance(token_expiry, str):
            try:
                token_expiry = datetime.fromisoformat(token_expiry.replace("Z", "+00:00"))
            except ValueError:
                return True
        if not isinstance(token_expiry, datetime):
            return True
        if token_expiry.tzinfo is None:
            token_expiry = token_expiry.replace(tzinfo=UTC)
        return datetime.now(UTC) >= (token_expiry - timedelta(minutes=5))

    async def _save_token(self, creds: dict[str, Any], access_token: str, expires_in: int) -> None:
        """Persist refreshed access token in connector credentials payload."""
        creds["access_token"] = access_token
        creds["token_expires_at"] = (datetime.now(UTC) + timedelta(seconds=int(expires_in))).isoformat()

    async def _refresh_token(self, creds: dict[str, Any]) -> str:
        refresh_token = creds.get("refresh_token")
        client_id = creds.get("client_id")
        client_secret = creds.get("client_secret")
        if not refresh_token or not client_id or not client_secret:
            raise AuthenticationError("Zoho refresh requires refresh_token, client_id and client_secret")

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                self.ZOHO_TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "refresh_token": refresh_token,
                },
            )
        data = response.json()
        if response.status_code >= 400 or "access_token" not in data:
            raise AuthenticationError(f"Zoho token refresh failed: {data}")

        token = str(data["access_token"])
        await self._save_token(creds, token, int(data.get("expires_in", 3600)))
        return token

    async def _get_valid_token(self, creds: dict[str, Any]) -> str:
        token = creds.get("access_token")
        if token and not self._token_is_expired(creds):
            return str(token)
        return await self._refresh_token(creds)

    def _parse_zoho_trial_balance(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        rows = payload.get("trialbalance") or payload.get("trial_balance") or payload.get("rows") or []
        if not isinstance(rows, list):
            return []
        parsed: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            amount = row.get("closing_balance")
            try:
                closing_balance = Decimal(str(amount or "0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            except (InvalidOperation, ValueError):
                closing_balance = Decimal("0.00")
            parsed.append({
                "account_name": str(row.get("account_name") or row.get("name") or ""),
                "account_code": str(row.get("account_code") or row.get("code") or ""),
                "closing_balance": closing_balance,
                "raw": row,
            })
        return parsed

    async def test_connection(self, credentials: dict[str, Any]) -> dict[str, Any]:
        token = await self._get_valid_token(credentials)
        organization_id = credentials.get("organization_id")
        if not organization_id:
            raise ExtractionError("Zoho organization_id is required")
        payload = await self._fetch(
            "organizations",
            access_token=token,
            base_url=self.ZOHO_API_BASE,
            params={"organization_id": organization_id},
        )
        return {
            "ok": True,
            "connector_type": self.connector_type.value,
            "organization_id": organization_id,
            "payload": payload,
        }

    async def extract_trial_balance(self, **kwargs: Any) -> dict[str, Any]:
        creds = dict(kwargs.get("credentials") or {})
        creds.update({k: v for k, v in kwargs.items() if k in {"access_token", "refresh_token", "client_id", "client_secret", "token_expires_at", "organization_id"} and v is not None})

        organization_id = creds.get("organization_id")
        if not organization_id:
            raise ExtractionError("Zoho organization_id is required")

        token = await self._get_valid_token(creds)
        from_date_value = kwargs.get("from_date")
        to_date_value = kwargs.get("to_date")
        from_date_str = from_date_value.isoformat() if isinstance(from_date_value, date) else str(from_date_value or "")
        to_date_str = to_date_value.isoformat() if isinstance(to_date_value, date) else str(to_date_value or "")

        payload = await self._fetch(
            "reports/trialbalance",
            access_token=token,
            base_url=self.ZOHO_API_BASE,
            params={
                "organization_id": organization_id,
                "from_date": from_date_str,
                "to_date": to_date_str,
            },
        )
        return {
            "dataset_type": DatasetType.TRIAL_BALANCE.value,
            "payload": payload,
            "records": self._parse_zoho_trial_balance(payload),
        }

    async def extract_general_ledger(self, **kwargs: Any) -> dict[str, Any]:
        creds = dict(kwargs.get("credentials") or {})
        creds.update({k: v for k, v in kwargs.items() if k in {"access_token", "refresh_token", "client_id", "client_secret", "token_expires_at", "organization_id"} and v is not None})

        organization_id = creds.get("organization_id")
        if not organization_id:
            raise ExtractionError("Zoho organization_id is required")

        token = await self._get_valid_token(creds)
        payload = await self._fetch(
            "reports/generalledger",
            access_token=token,
            base_url=self.ZOHO_API_BASE,
            params={"organization_id": organization_id},
        )
        return {"dataset_type": DatasetType.GENERAL_LEDGER.value, "payload": payload}
