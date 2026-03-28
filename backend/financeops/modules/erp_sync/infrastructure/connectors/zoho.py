from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, cast

import httpx

from financeops.modules.erp_sync.domain.enums import ConnectorType, DatasetType
from financeops.modules.erp_sync.infrastructure.connectors.base import (
    AbstractConnector,
    ExtractionError,
)
from financeops.modules.erp_sync.infrastructure.connectors.http_backoff import (
    with_backoff,
)
from financeops.modules.erp_sync.infrastructure.secret_store import secret_store


class AuthenticationError(ExtractionError):
    """Zoho authentication/token lifecycle failure."""


_DEFAULT_PAGE_SIZE = 200

_DATASET_CONFIG: dict[DatasetType, dict[str, Any]] = {
    DatasetType.TRIAL_BALANCE: {
        "endpoint": "reports/trialbalance",
        "paginated": False,
        "records_key": "trialbalance",
    },
    DatasetType.GENERAL_LEDGER: {
        "endpoint": "reports/generalledger",
        "paginated": False,
        "records_key": "generalledger",
    },
    DatasetType.PROFIT_AND_LOSS: {
        "endpoint": "reports/profitandloss",
        "paginated": False,
        "records_key": "profitandloss",
    },
    DatasetType.BALANCE_SHEET: {
        "endpoint": "reports/balancesheet",
        "paginated": False,
        "records_key": "balancesheet",
    },
    DatasetType.INVOICE_REGISTER: {
        "endpoint": "invoices",
        "paginated": True,
        "records_key": "invoices",
    },
    DatasetType.PURCHASE_REGISTER: {
        "endpoint": "bills",
        "paginated": True,
        "records_key": "bills",
    },
    DatasetType.CUSTOMER_MASTER: {
        "endpoint": "contacts",
        "paginated": True,
        "records_key": "contacts",
        "extra_params": {"contact_type": "customer"},
    },
    DatasetType.VENDOR_MASTER: {
        "endpoint": "contacts",
        "paginated": True,
        "records_key": "contacts",
        "extra_params": {"contact_type": "vendor"},
    },
    DatasetType.CHART_OF_ACCOUNTS: {
        "endpoint": "chartofaccounts",
        "paginated": True,
        "records_key": "chartofaccounts",
    },
    DatasetType.BANK_TRANSACTION_REGISTER: {
        "endpoint": "banktransactions",
        "paginated": True,
        "records_key": "banktransactions",
    },
    DatasetType.TAX_LEDGER: {
        "endpoint": "settings/taxes",
        "paginated": False,
        "records_key": "taxes",
    },
    DatasetType.TDS_REGISTER: {
        "endpoint": "reports/tdsreport",
        "paginated": False,
        "records_key": "tdsreport",
    },
    DatasetType.GST_RETURN_GSTR1: {
        "endpoint": "reports/gstr1",
        "paginated": False,
        "records_key": "gstr1",
    },
    DatasetType.GST_RETURN_GSTR3B: {
        "endpoint": "reports/gstr3b",
        "paginated": False,
        "records_key": "gstr3b",
    },
}


class ZohoConnector(AbstractConnector):
    connector_type = ConnectorType.ZOHO
    connector_version = "1.2.0"
    supports_resumable_extraction = True
    # CASH_FLOW_STATEMENT intentionally excluded.
    supported_datasets = set(_DATASET_CONFIG.keys())

    ZOHO_TOKEN_URL = "https://accounts.zoho.in/oauth/v2/token"
    ZOHO_API_BASE = "https://books.zoho.in/api/v3"

    @staticmethod
    def _decimal_or_zero(value: Any) -> Decimal:
        try:
            return Decimal(str(value or "0")).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        except (InvalidOperation, TypeError, ValueError):
            return Decimal("0.00")

    @staticmethod
    def _normalize_payload(value: Any) -> Any:
        if isinstance(value, dict):
            return {str(k): ZohoConnector._normalize_payload(v) for k, v in value.items()}
        if isinstance(value, list):
            return [ZohoConnector._normalize_payload(item) for item in value]
        if isinstance(value, float):
            return Decimal(str(value))
        return value

    async def _fetch(
        self,
        endpoint: str,
        *,
        access_token: str,
        base_url: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        headers = {"Authorization": f"Zoho-oauthtoken {access_token}"}
        url = f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await with_backoff(
                lambda: client.get(url, headers=headers, params=params or {}),
                context=f"ZOHO:{endpoint}",
            )
        if response.status_code in {401, 403}:
            raise AuthenticationError(
                f"Zoho API auth error ({response.status_code}) for {endpoint}"
            )
        if response.status_code >= 400:
            raise ExtractionError(
                f"Zoho API error ({response.status_code}) for {endpoint}"
            )
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
                token_expiry = datetime.fromisoformat(
                    token_expiry.replace("Z", "+00:00")
                )
            except ValueError:
                return True
        if not isinstance(token_expiry, datetime):
            return True
        if token_expiry.tzinfo is None:
            token_expiry = token_expiry.replace(tzinfo=UTC)
        return datetime.now(UTC) >= (token_expiry - timedelta(minutes=5))

    async def _save_token(
        self, creds: dict[str, Any], access_token: str, expires_in: int
    ) -> None:
        creds["access_token"] = access_token
        creds["token_expires_at"] = (
            datetime.now(UTC) + timedelta(seconds=int(expires_in))
        ).isoformat()

    async def _refresh_token(self, creds: dict[str, Any]) -> str:
        refresh_token = creds.get("refresh_token")
        client_id = creds.get("client_id")
        client_secret = creds.get("client_secret")
        if not refresh_token or not client_id or not client_secret:
            raise AuthenticationError(
                "Zoho refresh requires refresh_token, client_id and client_secret"
            )

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
        rows = payload.get("trialbalance") or payload.get("trial_balance") or []
        if not isinstance(rows, list):
            return []
        parsed: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            parsed.append(
                {
                    "account_name": str(row.get("account_name") or row.get("name") or ""),
                    "account_code": str(row.get("account_code") or row.get("code") or ""),
                    "closing_balance": self._decimal_or_zero(row.get("closing_balance")),
                    "raw": self._normalize_payload(row),
                }
            )
        return parsed

    async def _resolve_creds(self, kwargs: dict[str, Any]) -> tuple[dict[str, Any], str]:
        creds = dict(kwargs.get("credentials") or {})
        secret_ref = kwargs.get("secret_ref") or creds.get("secret_ref")
        if secret_ref:
            secret_payload = await secret_store.get_secret(str(secret_ref))
            if isinstance(secret_payload, dict):
                creds = {**secret_payload, **creds}

        for key in {
            "access_token",
            "refresh_token",
            "client_id",
            "client_secret",
            "token_expires_at",
            "organization_id",
        }:
            if key in kwargs and kwargs[key] is not None:
                creds[key] = kwargs[key]

        organization_id = str(
            kwargs.get("organization_id") or creds.get("organization_id") or ""
        ).strip()
        return creds, organization_id

    @staticmethod
    def _extract_records(payload: dict[str, Any], record_key: str | None) -> list[dict[str, Any]]:
        candidate_keys = [record_key] if record_key else []
        candidate_keys.extend(["records", "items", "rows", "data"])
        for key in candidate_keys:
            if not key:
                continue
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
            if isinstance(value, dict):
                row_list = value.get("Row")
                if isinstance(row_list, list):
                    return [item for item in row_list if isinstance(item, dict)]
        return []

    @staticmethod
    def _to_iso_date(value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, date):
            return value.isoformat()
        text = str(value).strip()
        return text or None

    def _build_envelope(
        self,
        *,
        dataset_type: DatasetType,
        payload: dict[str, Any],
        records: list[dict[str, Any]],
        is_resumable: bool,
        next_checkpoint: dict[str, Any] | None,
    ) -> dict[str, Any]:
        reported_count = payload.get("total_count", payload.get("count", len(records)))
        try:
            erp_reported_line_count = int(reported_count)
        except (TypeError, ValueError):
            erp_reported_line_count = len(records)
        return {
            "dataset_type": dataset_type.value,
            "payload": payload,
            "records": records,
            "line_count": len(records),
            "erp_reported_line_count": erp_reported_line_count,
            "is_resumable": is_resumable,
            "next_checkpoint": next_checkpoint,
        }

    async def _extract_non_paginated(
        self,
        *,
        dataset_type: DatasetType,
        config: dict[str, Any],
        access_token: str,
        organization_id: str,
        kwargs: dict[str, Any],
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"organization_id": organization_id}
        if "extra_params" in config and isinstance(config["extra_params"], dict):
            params.update(config["extra_params"])
        from_date = self._to_iso_date(kwargs.get("from_date"))
        to_date = self._to_iso_date(kwargs.get("to_date"))
        if from_date is not None:
            params["from_date"] = from_date
        if to_date is not None:
            params["to_date"] = to_date

        payload = await self._fetch(
            str(config["endpoint"]),
            access_token=access_token,
            base_url=self.ZOHO_API_BASE,
            params=params,
        )
        normalized_payload = self._normalize_payload(payload)
        if dataset_type == DatasetType.TRIAL_BALANCE:
            records = self._parse_zoho_trial_balance(normalized_payload)
        else:
            records = self._extract_records(
                normalized_payload, cast(str | None, config.get("records_key"))
            )
        return self._build_envelope(
            dataset_type=dataset_type,
            payload=normalized_payload,
            records=records,
            is_resumable=False,
            next_checkpoint=None,
        )

    async def _extract_paginated(
        self,
        *,
        dataset_type: DatasetType,
        config: dict[str, Any],
        access_token: str,
        organization_id: str,
        kwargs: dict[str, Any],
    ) -> dict[str, Any]:
        checkpoint = kwargs.get("checkpoint") or {}
        page = int(checkpoint.get("page") or kwargs.get("page") or 1)
        page_size = int(
            checkpoint.get("page_size")
            or kwargs.get("page_size")
            or _DEFAULT_PAGE_SIZE
        )

        params: dict[str, Any] = {
            "organization_id": organization_id,
            "page": page,
            "per_page": page_size,
        }
        if "extra_params" in config and isinstance(config["extra_params"], dict):
            params.update(config["extra_params"])
        from_date = self._to_iso_date(kwargs.get("from_date"))
        to_date = self._to_iso_date(kwargs.get("to_date"))
        if from_date is not None:
            params["from_date"] = from_date
        if to_date is not None:
            params["to_date"] = to_date

        payload = await self._fetch(
            str(config["endpoint"]),
            access_token=access_token,
            base_url=self.ZOHO_API_BASE,
            params=params,
        )
        normalized_payload = self._normalize_payload(payload)
        records = self._extract_records(
            normalized_payload, cast(str | None, config.get("records_key"))
        )
        page_context = normalized_payload.get("page_context")
        has_more_page = False
        if isinstance(page_context, dict):
            has_more_page = bool(page_context.get("has_more_page"))
        if not has_more_page and len(records) >= page_size:
            has_more_page = True

        next_checkpoint = (
            {"page": page + 1, "page_size": page_size} if has_more_page else None
        )
        return self._build_envelope(
            dataset_type=dataset_type,
            payload=normalized_payload,
            records=records,
            is_resumable=has_more_page,
            next_checkpoint=next_checkpoint,
        )

    async def extract(self, dataset_type: DatasetType, **kwargs: Any) -> dict[str, Any]:
        if isinstance(dataset_type, str):
            dataset_type = DatasetType(dataset_type)
        if dataset_type not in self.supported_datasets:
            self._unsupported(dataset_type)

        creds, organization_id = await self._resolve_creds(kwargs)
        if not organization_id:
            raise ExtractionError("Zoho organization_id is required")
        access_token = await self._get_valid_token(creds)
        config = _DATASET_CONFIG[dataset_type]
        if bool(config.get("paginated")):
            return await self._extract_paginated(
                dataset_type=dataset_type,
                config=config,
                access_token=access_token,
                organization_id=organization_id,
                kwargs=kwargs,
            )
        return await self._extract_non_paginated(
            dataset_type=dataset_type,
            config=config,
            access_token=access_token,
            organization_id=organization_id,
            kwargs=kwargs,
        )

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
        return await self.extract(DatasetType.TRIAL_BALANCE, **kwargs)

    async def extract_general_ledger(self, **kwargs: Any) -> dict[str, Any]:
        return await self.extract(DatasetType.GENERAL_LEDGER, **kwargs)

    async def extract_profit_and_loss(self, **kwargs: Any) -> dict[str, Any]:
        return await self.extract(DatasetType.PROFIT_AND_LOSS, **kwargs)

    async def extract_balance_sheet(self, **kwargs: Any) -> dict[str, Any]:
        return await self.extract(DatasetType.BALANCE_SHEET, **kwargs)

    async def extract_invoice_register(self, **kwargs: Any) -> dict[str, Any]:
        return await self.extract(DatasetType.INVOICE_REGISTER, **kwargs)

    async def extract_purchase_register(self, **kwargs: Any) -> dict[str, Any]:
        return await self.extract(DatasetType.PURCHASE_REGISTER, **kwargs)

    async def extract_customer_master(self, **kwargs: Any) -> dict[str, Any]:
        return await self.extract(DatasetType.CUSTOMER_MASTER, **kwargs)

    async def extract_vendor_master(self, **kwargs: Any) -> dict[str, Any]:
        return await self.extract(DatasetType.VENDOR_MASTER, **kwargs)

    async def extract_chart_of_accounts(self, **kwargs: Any) -> dict[str, Any]:
        return await self.extract(DatasetType.CHART_OF_ACCOUNTS, **kwargs)

    async def extract_bank_transaction_register(self, **kwargs: Any) -> dict[str, Any]:
        return await self.extract(DatasetType.BANK_TRANSACTION_REGISTER, **kwargs)

    async def extract_tax_ledger(self, **kwargs: Any) -> dict[str, Any]:
        return await self.extract(DatasetType.TAX_LEDGER, **kwargs)

    async def extract_tds_register(self, **kwargs: Any) -> dict[str, Any]:
        return await self.extract(DatasetType.TDS_REGISTER, **kwargs)

    async def extract_gst_return_gstr1(self, **kwargs: Any) -> dict[str, Any]:
        return await self.extract(DatasetType.GST_RETURN_GSTR1, **kwargs)

    async def extract_gst_return_gstr3b(self, **kwargs: Any) -> dict[str, Any]:
        return await self.extract(DatasetType.GST_RETURN_GSTR3B, **kwargs)
