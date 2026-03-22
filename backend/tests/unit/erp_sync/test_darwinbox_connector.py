from __future__ import annotations

import pytest

from financeops.modules.erp_sync.domain.enums import DatasetType
from financeops.modules.erp_sync.infrastructure.connectors.base import ConnectorCapabilityNotSupported
from financeops.modules.erp_sync.infrastructure.connectors.darwinbox import DarwinboxConnector


@pytest.mark.asyncio
async def test_darwinbox_capabilities_connection_and_extract() -> None:
    connector = DarwinboxConnector()
    assert DatasetType.STAFF_ADVANCES in connector.supported_datasets
    assert connector.supports_resumable_extraction is True

    async def fake_token(_: dict[str, object]) -> str:
        return "token"

    async def fake_request(*_, **__) -> dict[str, object]:
        return {"data": [{"id": "1", "amount": "500.00"}]}

    connector._resolve_access_token = fake_token  # type: ignore[method-assign]
    connector._request_json = fake_request  # type: ignore[method-assign]

    creds = {"api_key": "api", "base_url": "https://darwinbox"}
    connection = await connector.test_connection(creds)
    payload = await connector.extract(DatasetType.STAFF_ADVANCES, credentials=creds)
    assert connection["ok"] is True
    assert payload["dataset_type"] == DatasetType.STAFF_ADVANCES.value
    assert payload["records"]


@pytest.mark.asyncio
async def test_darwinbox_unsupported_dataset_raises() -> None:
    connector = DarwinboxConnector()
    with pytest.raises(ConnectorCapabilityNotSupported):
        await connector.extract(DatasetType.TRIAL_BALANCE, credentials={"api_key": "api", "base_url": "https://darwinbox"})

