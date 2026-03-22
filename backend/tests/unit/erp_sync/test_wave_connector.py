from __future__ import annotations

import pytest

from financeops.modules.erp_sync.domain.enums import DatasetType
from financeops.modules.erp_sync.infrastructure.connectors.base import ConnectorCapabilityNotSupported
from financeops.modules.erp_sync.infrastructure.connectors.wave import WaveConnector


@pytest.mark.asyncio
async def test_wave_capabilities_connection_and_extract() -> None:
    connector = WaveConnector()
    assert DatasetType.PROFIT_AND_LOSS in connector.supported_datasets
    assert connector.supports_resumable_extraction is True

    async def fake_token(_: dict[str, object]) -> str:
        return "token"

    async def fake_graphql(*_, **__) -> dict[str, object]:
        return {
            "data": {
                "business": {
                    "trialBalance": {
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                        "edges": [{"node": {"accountName": "Cash", "balance": "10.00"}}],
                    }
                }
            }
        }

    connector._resolve_access_token = fake_token  # type: ignore[method-assign]
    connector._graphql_request = fake_graphql  # type: ignore[method-assign]

    connection = await connector.test_connection({"client_id": "c", "client_secret": "s", "access_token": "t"})
    payload = await connector.extract(
        DatasetType.TRIAL_BALANCE,
        credentials={"client_id": "c", "client_secret": "s", "access_token": "t"},
    )
    assert connection["ok"] is True
    assert payload["dataset_type"] == DatasetType.TRIAL_BALANCE.value
    assert payload["records"]


@pytest.mark.asyncio
async def test_wave_unsupported_dataset_raises() -> None:
    connector = WaveConnector()
    with pytest.raises(ConnectorCapabilityNotSupported):
        await connector.extract(DatasetType.AP_AGEING, credentials={"client_id": "c"})

