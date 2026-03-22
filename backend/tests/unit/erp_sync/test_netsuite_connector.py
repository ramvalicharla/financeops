from __future__ import annotations

import pytest

from financeops.modules.erp_sync.domain.enums import DatasetType
from financeops.modules.erp_sync.infrastructure.connectors.base import ConnectorCapabilityNotSupported
from financeops.modules.erp_sync.infrastructure.connectors.netsuite import NetsuiteConnector


@pytest.mark.asyncio
async def test_netsuite_capabilities_connection_and_extract() -> None:
    connector = NetsuiteConnector()
    assert DatasetType.TRIAL_BALANCE in connector.supported_datasets
    assert DatasetType.PAYROLL_SUMMARY in connector.supported_datasets
    assert connector.supports_resumable_extraction is True

    async def fake_request(*_, **__) -> dict[str, object]:
        return {"items": [{"id": "1", "amount": "15.00"}]}

    connector._request_json = fake_request  # type: ignore[method-assign]

    connection = await connector.test_connection(
        {
            "account_id": "acc",
            "consumer_key": "ck",
            "consumer_secret": "cs",
            "token_id": "tk",
            "token_secret": "ts",
        }
    )
    payload = await connector.extract(
        DatasetType.GENERAL_LEDGER,
        credentials={
            "account_id": "acc",
            "consumer_key": "ck",
            "consumer_secret": "cs",
            "token_id": "tk",
            "token_secret": "ts",
        },
    )
    assert connection["ok"] is True
    assert payload["dataset_type"] == DatasetType.GENERAL_LEDGER.value
    assert "records" in payload


@pytest.mark.asyncio
async def test_netsuite_invalid_dataset_raises_with_enum_guard() -> None:
    connector = NetsuiteConnector()

    class _UnknownDataset:
        value = "unknown_dataset"

    with pytest.raises(ConnectorCapabilityNotSupported):
        await connector.extract(_UnknownDataset())  # type: ignore[arg-type]
