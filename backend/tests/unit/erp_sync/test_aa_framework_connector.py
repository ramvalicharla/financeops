from __future__ import annotations

import pytest

from financeops.modules.erp_sync.domain.enums import DatasetType
from financeops.modules.erp_sync.infrastructure.connectors.aa_framework import AaFrameworkConnector
from financeops.modules.erp_sync.infrastructure.connectors.base import ConnectorCapabilityNotSupported


@pytest.mark.asyncio
async def test_aa_framework_capabilities_connection_and_extract() -> None:
    connector = AaFrameworkConnector()
    assert DatasetType.BANK_TRANSACTION_REGISTER in connector.supported_datasets
    assert connector.supports_resumable_extraction is False

    async def fake_fetch(*_, **__) -> dict[str, object]:
        return {"transactions": [{"id": "1", "amount": "99.00"}]}

    connector._fetch_fi_payload = fake_fetch  # type: ignore[method-assign]

    base_credentials = {
        "aa_handle": "finvu",
        "client_id": "c",
        "client_secret": "s",
        "fip_id": "fip",
        "consent_artefact": "consent-1",
    }
    connection = await connector.test_connection(base_credentials)
    payload = await connector.extract(DatasetType.BANK_TRANSACTION_REGISTER, credentials=base_credentials)
    assert connection["ok"] is True
    assert payload["dataset_type"] == DatasetType.BANK_TRANSACTION_REGISTER.value
    assert payload["records"]


@pytest.mark.asyncio
async def test_aa_framework_unsupported_dataset_raises() -> None:
    connector = AaFrameworkConnector()
    with pytest.raises(ConnectorCapabilityNotSupported):
        await connector.extract(DatasetType.PAYROLL_SUMMARY, credentials={"aa_handle": "finvu"})

