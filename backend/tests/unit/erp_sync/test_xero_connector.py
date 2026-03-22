from __future__ import annotations

import pytest

from financeops.modules.erp_sync.domain.enums import DatasetType
from financeops.modules.erp_sync.infrastructure.connectors.base import ConnectorCapabilityNotSupported
from financeops.modules.erp_sync.infrastructure.connectors.xero import XeroConnector


@pytest.mark.asyncio
async def test_xero_capabilities_connection_and_extract() -> None:
    connector = XeroConnector()
    assert DatasetType.GENERAL_LEDGER in connector.supported_datasets
    assert connector.supports_resumable_extraction is True

    async def fake_token(_: dict[str, object]) -> str:
        return "token"

    async def fake_request(*_, **__) -> dict[str, object]:
        return {"Reports": [{"Rows": [{"Name": "Sales", "Amount": "100.00"}]}]}

    connector._resolve_access_token = fake_token  # type: ignore[method-assign]
    connector._request_json = fake_request  # type: ignore[method-assign]

    connection = await connector.test_connection(
        {"client_id": "c", "client_secret": "s", "tenant_id": "t", "refresh_token": "rt"}
    )
    payload = await connector.extract(
        DatasetType.TRIAL_BALANCE,
        credentials={"client_id": "c", "client_secret": "s", "tenant_id": "t", "refresh_token": "rt"},
    )
    assert connection["ok"] is True
    assert payload["dataset_type"] == DatasetType.TRIAL_BALANCE.value
    assert "records" in payload


@pytest.mark.asyncio
async def test_xero_unsupported_dataset_raises() -> None:
    connector = XeroConnector()
    with pytest.raises(ConnectorCapabilityNotSupported):
        await connector.extract(DatasetType.PAYROLL_SUMMARY, credentials={"client_id": "c"})

