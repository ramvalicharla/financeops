from __future__ import annotations

from decimal import Decimal

import pytest

from financeops.modules.erp_sync.domain.enums import DatasetType
from financeops.modules.erp_sync.infrastructure.connectors.base import ConnectorCapabilityNotSupported
from financeops.modules.erp_sync.infrastructure.connectors.razorpay import RazorpayConnector


@pytest.mark.asyncio
async def test_razorpay_capabilities_connection_and_extract() -> None:
    connector = RazorpayConnector()
    assert DatasetType.BANK_TRANSACTION_REGISTER in connector.supported_datasets
    assert connector.supports_resumable_extraction is True

    async def fake_request(*_, **__) -> dict[str, object]:
        return {"items": [{"id": "setl_1", "amount": 12345, "created_at": 1700000000}]}

    connector._request_json = fake_request  # type: ignore[method-assign]

    connection = await connector.test_connection({"key_id": "k", "key_secret": "s"})
    payload = await connector.extract(
        DatasetType.BANK_STATEMENT,
        credentials={"key_id": "k", "key_secret": "s"},
        checkpoint={"from_timestamp": 1, "count": 100},
    )
    assert connection["ok"] is True
    assert payload["dataset_type"] == DatasetType.BANK_STATEMENT.value
    assert payload["records"][0]["amount"] == Decimal("123.45")


@pytest.mark.asyncio
async def test_razorpay_unsupported_dataset_raises() -> None:
    connector = RazorpayConnector()
    with pytest.raises(ConnectorCapabilityNotSupported):
        await connector.extract(DatasetType.PAYROLL_SUMMARY, credentials={"key_id": "k"})

