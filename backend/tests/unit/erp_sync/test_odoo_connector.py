from __future__ import annotations

import pytest

from financeops.modules.erp_sync.domain.enums import DatasetType
from financeops.modules.erp_sync.infrastructure.connectors.base import ConnectorCapabilityNotSupported
from financeops.modules.erp_sync.infrastructure.connectors.odoo import OdooConnector


@pytest.mark.asyncio
async def test_odoo_capabilities_connection_and_extract() -> None:
    connector = OdooConnector()
    assert DatasetType.INVENTORY_REGISTER in connector.supported_datasets
    assert connector.supports_resumable_extraction is True

    async def fake_auth(_: dict[str, object]) -> int:
        return 9

    async def fake_call(*_, **__) -> list[dict[str, object]]:
        return [{"account_id": 1, "debit": "10.00"}]

    connector._authenticate = fake_auth  # type: ignore[method-assign]
    connector._call_kw = fake_call  # type: ignore[method-assign]

    connection = await connector.test_connection(
        {"url": "https://odoo", "database": "db", "username": "u", "api_key": "k"}
    )
    payload = await connector.extract(
        DatasetType.TRIAL_BALANCE,
        credentials={"url": "https://odoo", "database": "db", "username": "u", "api_key": "k"},
    )
    assert connection["ok"] is True
    assert payload["dataset_type"] == DatasetType.TRIAL_BALANCE.value
    assert payload["records"]


@pytest.mark.asyncio
async def test_odoo_unsupported_dataset_raises() -> None:
    connector = OdooConnector()
    with pytest.raises(ConnectorCapabilityNotSupported):
        await connector.extract(DatasetType.PAYROLL_SUMMARY, credentials={"url": "https://odoo"})

