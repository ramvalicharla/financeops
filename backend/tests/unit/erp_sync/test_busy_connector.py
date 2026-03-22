from __future__ import annotations

from decimal import Decimal

import pytest

from financeops.modules.erp_sync.domain.enums import DatasetType
from financeops.modules.erp_sync.infrastructure.connectors.base import (
    ConnectorCapabilityNotSupported,
    ExtractionError,
)
from financeops.modules.erp_sync.infrastructure.connectors.busy import BusyConnector


class _FakeSecretStore:
    async def get_secret(self, secret_ref: str) -> dict[str, str]:
        return {"api_key": "busy_key", "busy_host": "localhost", "busy_port": 8080}


@pytest.mark.asyncio
async def test_busy_test_connection_uses_health_endpoint() -> None:
    connector = BusyConnector(secret_store=_FakeSecretStore())

    async def fake_request_json(credentials, endpoint, *, params):
        assert endpoint == "/api/v1/health"
        assert credentials["api_key"] == "busy_key"
        return {"status": "ok"}

    connector._request_json = fake_request_json  # type: ignore[method-assign]
    result = await connector.test_connection({"api_key": "busy_key", "busy_host": "localhost", "busy_port": 8080})
    assert result["ok"] is True
    assert result["connector_type"] == "busy"


@pytest.mark.asyncio
async def test_busy_extract_trial_balance_with_checkpoint() -> None:
    connector = BusyConnector(secret_store=_FakeSecretStore())

    async def fake_request_json(credentials, endpoint, *, params):
        if endpoint.endswith("/summary"):
            return {"total_debit": "1,200.50", "total_credit": "1,200.50"}
        assert endpoint == "/api/v1/reports/trial-balance"
        assert params["page"] == 3
        return {
            "records": [{"account_code": "1001", "closing_debit": "1,200.50"}],
            "has_more": True,
            "next_page": 4,
            "last_id": "TB_1200",
            "total_count": 1,
        }

    connector._request_json = fake_request_json  # type: ignore[method-assign]
    payload = await connector.extract(
        DatasetType.TRIAL_BALANCE,
        secret_ref="secret://busy",
        checkpoint={"page": 3, "last_id": "TB_1100"},
    )
    assert payload["dataset_type"] == "trial_balance"
    assert payload["next_checkpoint"] == {"page": 4, "last_id": "TB_1200", "page_size": 100}
    assert payload["records"][0]["closing_debit"] == Decimal("1200.50")
    assert payload["erp_control_totals"]["total_debit"] == Decimal("1200.50")


@pytest.mark.asyncio
async def test_busy_extract_requires_api_key() -> None:
    connector = BusyConnector()
    with pytest.raises(ExtractionError, match="API key"):
        await connector.extract(DatasetType.TRIAL_BALANCE, credentials={"busy_host": "localhost"})


@pytest.mark.asyncio
async def test_busy_unsupported_dataset_raises_capability() -> None:
    connector = BusyConnector(secret_store=_FakeSecretStore())
    with pytest.raises(ConnectorCapabilityNotSupported):
        await connector.extract(DatasetType.PAYROLL_SUMMARY, secret_ref="secret://busy")
