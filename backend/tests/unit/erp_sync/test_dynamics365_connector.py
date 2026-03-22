from __future__ import annotations

import pytest

from financeops.modules.erp_sync.domain.enums import DatasetType
from financeops.modules.erp_sync.infrastructure.connectors.base import ConnectorCapabilityNotSupported
from financeops.modules.erp_sync.infrastructure.connectors.dynamics365 import Dynamics365Connector


@pytest.mark.asyncio
async def test_dynamics365_capabilities_connection_and_extract() -> None:
    connector = Dynamics365Connector()
    assert DatasetType.FIXED_ASSET_REGISTER in connector.supported_datasets
    assert connector.supports_resumable_extraction is True

    async def fake_token(_: dict[str, object]) -> str:
        return "token"

    async def fake_request(*_, **__) -> dict[str, object]:
        return {"value": [{"id": "1", "amount": "12.34"}]}

    connector._resolve_access_token = fake_token  # type: ignore[method-assign]
    connector._request_json = fake_request  # type: ignore[method-assign]

    connection = await connector.test_connection(
        {"tenant_id": "t", "client_id": "c", "client_secret": "s", "environment_url": "https://dynamics"}
    )
    payload = await connector.extract(
        DatasetType.GENERAL_LEDGER,
        credentials={"tenant_id": "t", "client_id": "c", "client_secret": "s", "environment_url": "https://dynamics"},
    )
    assert connection["ok"] is True
    assert payload["dataset_type"] == DatasetType.GENERAL_LEDGER.value
    assert payload["records"]


@pytest.mark.asyncio
async def test_dynamics365_unsupported_dataset_raises() -> None:
    connector = Dynamics365Connector()
    with pytest.raises(ConnectorCapabilityNotSupported):
        await connector.extract(DatasetType.PAYROLL_SUMMARY, credentials={"tenant_id": "t"})

