from __future__ import annotations

import pytest

from financeops.modules.erp_sync.domain.enums import DatasetType
from financeops.modules.erp_sync.infrastructure.connectors.base import ConnectorCapabilityNotSupported
from financeops.modules.erp_sync.infrastructure.connectors.keka import KekaConnector


@pytest.mark.asyncio
async def test_keka_capabilities_connection_and_extract() -> None:
    connector = KekaConnector()
    assert DatasetType.PAYROLL_SUMMARY in connector.supported_datasets
    assert connector.supports_resumable_extraction is True

    async def fake_request(*_, **__) -> dict[str, object]:
        return {"data": [{"employee": "E-1", "amount": "2000.00"}]}

    connector._request_json = fake_request  # type: ignore[method-assign]

    connection = await connector.test_connection({"api_key": "api", "base_url": "https://keka"})
    payload = await connector.extract(
        DatasetType.PAYROLL_SUMMARY,
        credentials={"api_key": "api", "base_url": "https://keka"},
    )
    assert connection["ok"] is True
    assert payload["dataset_type"] == DatasetType.PAYROLL_SUMMARY.value
    assert payload["records"]


@pytest.mark.asyncio
async def test_keka_unsupported_dataset_raises() -> None:
    connector = KekaConnector()
    with pytest.raises(ConnectorCapabilityNotSupported):
        await connector.extract(DatasetType.TRIAL_BALANCE, credentials={"api_key": "api", "base_url": "https://keka"})

