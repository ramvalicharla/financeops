from __future__ import annotations

from decimal import Decimal

import pytest

from financeops.modules.erp_sync.domain.enums import DatasetType
from financeops.modules.erp_sync.infrastructure.connectors.base import ConnectorCapabilityNotSupported
from financeops.modules.erp_sync.infrastructure.connectors.sap import SapConnector


@pytest.mark.asyncio
async def test_sap_s4hana_profile_connection_and_extract() -> None:
    connector = SapConnector()
    capabilities = await connector.declare_capabilities()
    assert capabilities.implementation_status == "live"
    assert DatasetType.TRIAL_BALANCE in capabilities.supported_datasets

    async def fake_token(_: dict[str, object]) -> str:
        return "token"

    async def fake_s4_fetch(*_, **__) -> dict[str, object]:
        return {"value": [{"id": "1", "total_balance": "10.00"}]}

    connector._resolve_s4_access_token = fake_token  # type: ignore[method-assign]
    connector._fetch_s4_payload = fake_s4_fetch  # type: ignore[method-assign]

    creds = {"sap_profile": "SAP_S4HANA_CLOUD", "api_base_url": "https://sap", "token_url": "https://token", "client_id": "c", "client_secret": "s"}
    connection = await connector.test_connection(creds)
    payload = await connector.extract(DatasetType.TRIAL_BALANCE, credentials=creds)
    assert connection["ok"] is True
    assert payload["dataset_type"] == DatasetType.TRIAL_BALANCE.value
    assert payload["records"][0]["total_balance"] == Decimal("10.00")


@pytest.mark.asyncio
async def test_sap_ecc_profile_connection_and_extract() -> None:
    connector = SapConnector()

    async def fake_ecc_fetch(*_, **__) -> dict[str, object]:
        return {"records": [{"id": "1", "debit": "20.00"}]}

    connector._fetch_ecc_payload = fake_ecc_fetch  # type: ignore[method-assign]

    creds = {"sap_profile": "SAP_ECC_ONPREMISE", "sap_host": "localhost", "sap_username": "u", "sap_password": "p"}
    connection = await connector.test_connection(creds)
    payload = await connector.extract(DatasetType.GENERAL_LEDGER, credentials=creds)
    assert connection["ok"] is True
    assert payload["dataset_type"] == DatasetType.GENERAL_LEDGER.value
    assert payload["records"]


@pytest.mark.asyncio
async def test_sap_unsupported_dataset_guard_raises() -> None:
    connector = SapConnector()

    class _UnknownDataset:
        value = "unknown_dataset"

    with pytest.raises(ConnectorCapabilityNotSupported):
        await connector.extract(_UnknownDataset())  # type: ignore[arg-type]
