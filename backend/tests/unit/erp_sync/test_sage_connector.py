from __future__ import annotations

import pytest

from financeops.modules.erp_sync.domain.enums import DatasetType
from financeops.modules.erp_sync.infrastructure.connectors.base import ConnectorCapabilityNotSupported
from financeops.modules.erp_sync.infrastructure.connectors.sage import SageConnector


@pytest.mark.asyncio
async def test_sage_capabilities_connection_and_extract() -> None:
    connector = SageConnector()
    assert DatasetType.ACCOUNTS_PAYABLE in connector.supported_datasets
    assert connector.supports_resumable_extraction is True

    async def fake_token(_: dict[str, object]) -> str:
        return "token"

    async def fake_sbc(*_, **__) -> dict[str, object]:
        return {"$items": [{"id": "1", "amount": "9.00"}]}

    connector._resolve_sbc_access_token = fake_token  # type: ignore[method-assign]
    connector._sbc_request_json = fake_sbc  # type: ignore[method-assign]

    connection = await connector.test_connection(
        {
            "sage_product": "SAGE_BUSINESS_CLOUD",
            "client_id": "c",
            "client_secret": "s",
            "refresh_token": "rt",
        }
    )
    payload = await connector.extract(
        DatasetType.TRIAL_BALANCE,
        credentials={
            "sage_product": "SAGE_BUSINESS_CLOUD",
            "client_id": "c",
            "client_secret": "s",
            "refresh_token": "rt",
        },
    )
    assert connection["ok"] is True
    assert payload["dataset_type"] == DatasetType.TRIAL_BALANCE.value
    assert "records" in payload


@pytest.mark.asyncio
async def test_sage_unsupported_dataset_raises() -> None:
    connector = SageConnector()
    with pytest.raises(ConnectorCapabilityNotSupported):
        await connector.extract(DatasetType.PAYROLL_SUMMARY, credentials={"sage_product": "SAGE_BUSINESS_CLOUD"})

