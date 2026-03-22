from __future__ import annotations

import pytest

from financeops.modules.erp_sync.domain.enums import DatasetType
from financeops.modules.erp_sync.infrastructure.connectors.base import ConnectorCapabilityNotSupported
from financeops.modules.erp_sync.infrastructure.connectors.freshbooks import FreshbooksConnector


@pytest.mark.asyncio
async def test_freshbooks_capabilities_connection_and_extract() -> None:
    connector = FreshbooksConnector()
    assert DatasetType.EXPENSE_CLAIMS in connector.supported_datasets
    assert connector.supports_resumable_extraction is True

    async def fake_token(_: dict[str, object]) -> str:
        return "token"

    async def fake_request(*_, **__) -> dict[str, object]:
        return {"items": [{"id": "1", "amount": "42.10"}]}

    connector._resolve_access_token = fake_token  # type: ignore[method-assign]
    connector._request_json = fake_request  # type: ignore[method-assign]

    connection = await connector.test_connection(
        {"client_id": "c", "client_secret": "s", "account_id": "a", "refresh_token": "rt"}
    )
    payload = await connector.extract(
        DatasetType.EXPENSE_CLAIMS,
        credentials={"client_id": "c", "client_secret": "s", "account_id": "a", "refresh_token": "rt"},
    )
    assert connection["ok"] is True
    assert payload["dataset_type"] == DatasetType.EXPENSE_CLAIMS.value
    assert "records" in payload


@pytest.mark.asyncio
async def test_freshbooks_unsupported_dataset_raises() -> None:
    connector = FreshbooksConnector()
    with pytest.raises(ConnectorCapabilityNotSupported):
        await connector.extract(DatasetType.BALANCE_SHEET, credentials={"client_id": "c"})

