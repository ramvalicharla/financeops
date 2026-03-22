from __future__ import annotations

from decimal import Decimal

import pytest

from financeops.modules.erp_sync.domain.enums import DatasetType
from financeops.modules.erp_sync.infrastructure.connectors.base import ConnectorCapabilityNotSupported
from financeops.modules.erp_sync.infrastructure.connectors.razorpay_payroll import RazorpayPayrollConnector


@pytest.mark.asyncio
async def test_razorpay_payroll_capabilities_connection_and_extract() -> None:
    connector = RazorpayPayrollConnector()
    assert DatasetType.PAYROLL_SUMMARY in connector.supported_datasets
    assert connector.supports_resumable_extraction is False

    async def fake_request(*_, **__) -> dict[str, object]:
        return {"items": [{"id": "1", "gross_amount": 100500}]}

    connector._request_json = fake_request  # type: ignore[method-assign]

    creds = {"key_id": "k", "key_secret": "s"}
    connection = await connector.test_connection(creds)
    payload = await connector.extract(DatasetType.PAYROLL_SUMMARY, credentials=creds)
    assert connection["ok"] is True
    assert payload["dataset_type"] == DatasetType.PAYROLL_SUMMARY.value
    assert payload["records"][0]["gross_amount"] == Decimal("1005.00")


@pytest.mark.asyncio
async def test_razorpay_payroll_unsupported_dataset_raises() -> None:
    connector = RazorpayPayrollConnector()
    with pytest.raises(ConnectorCapabilityNotSupported):
        await connector.extract(DatasetType.TRIAL_BALANCE, credentials={"key_id": "k", "key_secret": "s"})

