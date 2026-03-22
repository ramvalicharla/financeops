from __future__ import annotations

from typing import Any

import httpx

from financeops.modules.erp_sync.domain.enums import ConnectorType, DatasetType
from financeops.modules.erp_sync.infrastructure.connectors.base import AbstractConnector, ExtractionError


class ZohoConnector(AbstractConnector):
    connector_type = ConnectorType.ZOHO
    connector_version = "1.0.0"
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

    async def _fetch(self, endpoint: str, *, access_token: str, base_url: str) -> dict[str, Any]:
        headers = {"Authorization": f"Zoho-oauthtoken {access_token}"}
        url = f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers)
        if response.status_code >= 400:
            raise ExtractionError(f"Zoho API error ({response.status_code}) for {endpoint}")
        payload = response.json()
        if not isinstance(payload, dict):
            raise ExtractionError("Unexpected Zoho payload format")
        return payload

    async def extract_trial_balance(self, **kwargs: Any) -> dict[str, Any]:
        access_token = kwargs.get("access_token", "")
        base_url = kwargs.get("base_url", "https://www.zohoapis.com/books/v3")
        if not access_token:
            raise ExtractionError("Zoho access_token is required")
        payload = await self._fetch("reports/trialbalance", access_token=access_token, base_url=base_url)
        return {"dataset_type": DatasetType.TRIAL_BALANCE.value, "payload": payload}

    async def extract_general_ledger(self, **kwargs: Any) -> dict[str, Any]:
        access_token = kwargs.get("access_token", "")
        base_url = kwargs.get("base_url", "https://www.zohoapis.com/books/v3")
        if not access_token:
            raise ExtractionError("Zoho access_token is required")
        payload = await self._fetch("reports/generalledger", access_token=access_token, base_url=base_url)
        return {"dataset_type": DatasetType.GENERAL_LEDGER.value, "payload": payload}
