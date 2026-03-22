from __future__ import annotations

import pytest

from financeops.modules.erp_sync.domain.enums import DatasetType
from financeops.modules.erp_sync.infrastructure.connectors.base import ConnectorCapabilityNotSupported
from financeops.modules.erp_sync.infrastructure.connectors.quickbooks import QuickbooksConnector


@pytest.mark.asyncio
async def test_quickbooks_capabilities_connection_and_extract() -> None:
    connector = QuickbooksConnector()
    assert DatasetType.TRIAL_BALANCE in connector.supported_datasets
    assert connector.supports_resumable_extraction is True

    async def fake_token(_: dict[str, object]) -> str:
        return "token"

    async def fake_request(*_, **__) -> dict[str, object]:
        return {"Rows": {"Row": [{"account": "1000", "amount": "10.00"}]}, "totalCount": 1}

    connector._resolve_access_token = fake_token  # type: ignore[method-assign]
    connector._request_json = fake_request  # type: ignore[method-assign]

    connection = await connector.test_connection(
        {"client_id": "c", "client_secret": "s", "realm_id": "r", "refresh_token": "rt"}
    )
    payload = await connector.extract(
        DatasetType.TRIAL_BALANCE,
        credentials={"client_id": "c", "client_secret": "s", "realm_id": "r", "refresh_token": "rt"},
    )
    assert connection["ok"] is True
    assert payload["dataset_type"] == DatasetType.TRIAL_BALANCE.value
    assert "records" in payload


@pytest.mark.asyncio
async def test_quickbooks_unsupported_dataset_raises() -> None:
    connector = QuickbooksConnector()
    with pytest.raises(ConnectorCapabilityNotSupported):
        await connector.extract(DatasetType.PAYROLL_SUMMARY, credentials={"client_id": "c"})

