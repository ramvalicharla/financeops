from __future__ import annotations

from decimal import Decimal

import pytest

from financeops.modules.erp_sync.domain.enums import DatasetType
from financeops.modules.erp_sync.infrastructure.connectors.base import ConnectorCapabilityNotSupported
from financeops.modules.erp_sync.infrastructure.connectors.oracle import OracleConnector


@pytest.mark.asyncio
async def test_oracle_fusion_profile_connection_and_extract() -> None:
    connector = OracleConnector()
    capabilities = await connector.declare_capabilities()
    assert capabilities.implementation_status == "live"
    assert DatasetType.TRIAL_BALANCE in capabilities.supported_datasets

    async def fake_token(_: dict[str, object]) -> str:
        return "fusion-token"

    async def fake_fusion_fetch(*_, **__) -> dict[str, object]:
        return {"items": [{"balance_total": "100.50"}]}

    connector._resolve_fusion_access_token = fake_token  # type: ignore[method-assign]
    connector._fetch_fusion_payload = fake_fusion_fetch  # type: ignore[method-assign]

    creds = {
        "oracle_profile": "ORACLE_FUSION_CLOUD",
        "api_base_url": "https://oracle-fusion.example.com",
        "token_url": "https://token.example.com",
        "client_id": "client",
        "client_secret": "secret",
    }

    connection = await connector.test_connection(creds)
    payload = await connector.extract(DatasetType.TRIAL_BALANCE, credentials=creds)

    assert connection["ok"] is True
    assert connection["oracle_profile"] == "ORACLE_FUSION_CLOUD"
    assert payload["dataset_type"] == DatasetType.TRIAL_BALANCE.value
    assert payload["records"][0]["balance_total"] == Decimal("100.50")


@pytest.mark.asyncio
async def test_oracle_ebs_profile_connection_and_extract() -> None:
    connector = OracleConnector()

    async def fake_ebs_fetch(*_, **__) -> dict[str, object]:
        return {"records": [{"debit_total": "20.00"}]}

    connector._fetch_ebs_payload = fake_ebs_fetch  # type: ignore[method-assign]

    creds = {
        "oracle_profile": "ORACLE_EBS_ONPREMISE",
        "ebs_host": "localhost",
        "ebs_username": "user",
        "ebs_password": "pass",
    }

    connection = await connector.test_connection(creds)
    payload = await connector.extract(DatasetType.GENERAL_LEDGER, credentials=creds)

    assert connection["ok"] is True
    assert connection["oracle_profile"] == "ORACLE_EBS_ONPREMISE"
    assert payload["dataset_type"] == DatasetType.GENERAL_LEDGER.value
    assert payload["records"][0]["debit_total"] == Decimal("20.00")


@pytest.mark.asyncio
async def test_oracle_unsupported_dataset_guard_raises() -> None:
    connector = OracleConnector()

    class _UnknownDataset:
        value = "unknown_dataset"

    with pytest.raises(ConnectorCapabilityNotSupported):
        await connector.extract(_UnknownDataset())  # type: ignore[arg-type]
