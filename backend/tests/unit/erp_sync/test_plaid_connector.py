from __future__ import annotations

from decimal import Decimal

import pytest

from financeops.modules.erp_sync.domain.enums import DatasetType
from financeops.modules.erp_sync.infrastructure.connectors.base import ConnectorCapabilityNotSupported
from financeops.modules.erp_sync.infrastructure.connectors.plaid import PlaidConnector


@pytest.mark.asyncio
async def test_plaid_capabilities_connection_and_extract() -> None:
    connector = PlaidConnector()
    assert DatasetType.BANK_STATEMENT in connector.supported_datasets
    assert connector.supports_resumable_extraction is True

    async def fake_request(credentials, *, endpoint, body):  # type: ignore[no-untyped-def]
        if endpoint == "/accounts/balance/get":
            return {"accounts": [{"balances": {"current": "12.50"}}]}
        if endpoint == "/transactions/sync":
            return {"added": [{"transaction_id": "tx_1", "amount": "10.00"}], "next_cursor": "cur_1"}
        return {"item": {"item_id": "it_1"}}

    connector._request_json = fake_request  # type: ignore[method-assign]

    creds = {"client_id": "c", "secret": "s", "access_token": "a", "environment": "sandbox"}
    connection = await connector.test_connection(creds)
    payload = await connector.extract(DatasetType.BANK_STATEMENT, credentials=creds)
    assert connection["ok"] is True
    assert payload["dataset_type"] == DatasetType.BANK_STATEMENT.value
    assert payload["erp_control_totals"]["total_account_balance"] == Decimal("12.50")


@pytest.mark.asyncio
async def test_plaid_unsupported_dataset_raises() -> None:
    connector = PlaidConnector()
    with pytest.raises(ConnectorCapabilityNotSupported):
        await connector.extract(DatasetType.PAYROLL_SUMMARY, credentials={"client_id": "c"})

