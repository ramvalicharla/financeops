from __future__ import annotations

from decimal import Decimal

import pytest

from financeops.modules.erp_sync.domain.enums import DatasetType
from financeops.modules.erp_sync.infrastructure.connectors.base import ConnectorCapabilityNotSupported
from financeops.modules.erp_sync.infrastructure.connectors.stripe import StripeConnector


@pytest.mark.asyncio
async def test_stripe_capabilities_connection_and_extract() -> None:
    connector = StripeConnector()
    assert DatasetType.BANK_STATEMENT in connector.supported_datasets
    assert connector.supports_resumable_extraction is True

    async def fake_request(*_, **__) -> dict[str, object]:
        return {"data": [{"id": "po_1", "amount": 1500, "currency": "usd"}], "has_more": False}

    connector._request_json = fake_request  # type: ignore[method-assign]

    connection = await connector.test_connection({"secret_key": "sk_test"})
    payload = await connector.extract(DatasetType.BANK_STATEMENT, credentials={"secret_key": "sk_test"})
    assert connection["ok"] is True
    assert payload["dataset_type"] == DatasetType.BANK_STATEMENT.value
    assert payload["records"][0]["amount"] == Decimal("15.00")


@pytest.mark.asyncio
async def test_stripe_unsupported_dataset_raises() -> None:
    connector = StripeConnector()
    with pytest.raises(ConnectorCapabilityNotSupported):
        await connector.extract(DatasetType.PAYROLL_SUMMARY, credentials={"secret_key": "sk_test"})

