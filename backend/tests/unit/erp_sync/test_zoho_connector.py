from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from financeops.modules.erp_sync.domain.enums import DatasetType
from financeops.modules.erp_sync.infrastructure.connectors.base import (
    ConnectorCapabilityNotSupported,
)
from financeops.modules.erp_sync.infrastructure.connectors.zoho import (
    ZohoConnector,
    _DATASET_CONFIG,
)


class _DummyResponse:
    def __init__(self, status_code: int, payload: dict[str, Any]):
        self.status_code = status_code
        self._payload = payload
        self.headers: dict[str, str] = {}

    def json(self) -> dict[str, Any]:
        return self._payload


class _DummyClient:
    def __init__(
        self,
        post_response: _DummyResponse | None = None,
        get_response: _DummyResponse | None = None,
    ):
        self._post_response = post_response
        self._get_response = get_response

    async def __aenter__(self) -> "_DummyClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def post(self, *args, **kwargs) -> _DummyResponse:
        assert self._post_response is not None
        return self._post_response

    async def get(self, *args, **kwargs) -> _DummyResponse:
        assert self._get_response is not None
        return self._get_response


@pytest.fixture
def connector() -> ZohoConnector:
    return ZohoConnector()


@pytest.fixture
def base_credentials() -> dict[str, Any]:
    return {
        "access_token": "token",
        "organization_id": "org-1",
        "token_expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
    }


class TestZohoContract:
    def test_supported_dataset_count(self, connector: ZohoConnector) -> None:
        assert len(connector.supported_datasets) == 14

    def test_cash_flow_removed(self, connector: ZohoConnector) -> None:
        assert DatasetType.CASH_FLOW_STATEMENT not in connector.supported_datasets

    @pytest.mark.parametrize("dataset", list(_DATASET_CONFIG.keys()))
    def test_all_supported_have_config(self, dataset: DatasetType) -> None:
        assert dataset in _DATASET_CONFIG


class TestZohoTokenLifecycle:
    @pytest.mark.asyncio
    async def test_token_refresh_on_expiry(self, monkeypatch: pytest.MonkeyPatch) -> None:
        creds = {
            "access_token": "expired",
            "refresh_token": "refresh",
            "client_id": "client",
            "client_secret": "secret",
            "token_expires_at": (datetime.now(UTC) - timedelta(minutes=1)).isoformat(),
        }
        async def fake_post_form_request(*, url: str, data: dict[str, Any], timeout: float = 30.0) -> _DummyResponse:
            _ = (url, data, timeout)
            return _DummyResponse(200, {"access_token": "new-token", "expires_in": 3600})

        monkeypatch.setattr(
            "financeops.modules.erp_sync.infrastructure.connectors.zoho.post_form_request",
            fake_post_form_request,
        )
        token = await ZohoConnector()._get_valid_token(creds)
        assert token == "new-token"
        assert creds["access_token"] == "new-token"


class TestZohoExtract:
    @pytest.mark.asyncio
    async def test_missing_organization_id_raises(self, connector: ZohoConnector) -> None:
        with pytest.raises(Exception, match="organization_id"):
            await connector.extract(DatasetType.TRIAL_BALANCE, credentials={"access_token": "t"})

    @pytest.mark.asyncio
    async def test_unsupported_dataset_raises(self, connector: ZohoConnector) -> None:
        with pytest.raises(ConnectorCapabilityNotSupported):
            await connector.extract(DatasetType.PAYROLL_SUMMARY, credentials={"access_token": "t", "organization_id": "o"})

    @pytest.mark.asyncio
    async def test_trial_balance_envelope(self, connector: ZohoConnector, base_credentials: dict[str, Any]) -> None:
        async def fake_fetch(endpoint: str, *, access_token: str, base_url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
            assert endpoint == "reports/trialbalance"
            return {
                "trialbalance": [
                    {"account_name": "Cash", "account_code": "1001", "closing_balance": "123.45"}
                ]
            }

        with patch.object(connector, "_fetch", side_effect=fake_fetch):
            result = await connector.extract(DatasetType.TRIAL_BALANCE, credentials=base_credentials)

        expected_keys = {
            "dataset_type",
            "payload",
            "records",
            "line_count",
            "erp_reported_line_count",
            "is_resumable",
            "next_checkpoint",
        }
        assert expected_keys.issubset(set(result.keys()))
        assert result["dataset_type"] == DatasetType.TRIAL_BALANCE.value
        assert len(result["records"]) == 1
        assert result["records"][0]["closing_balance"] == Decimal("123.45")

    @pytest.mark.asyncio
    async def test_paginated_sets_next_checkpoint(
        self,
        connector: ZohoConnector,
        base_credentials: dict[str, Any],
    ) -> None:
        async def fake_fetch(endpoint: str, *, access_token: str, base_url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
            assert endpoint == "invoices"
            assert params is not None
            assert params["page"] == 1
            return {
                "invoices": [{"invoice_id": "1"}],
                "page_context": {"has_more_page": True},
            }

        with patch.object(connector, "_fetch", side_effect=fake_fetch):
            result = await connector.extract(DatasetType.INVOICE_REGISTER, credentials=base_credentials)

        assert result["is_resumable"] is True
        assert result["next_checkpoint"] == {"page": 2, "page_size": 200}

    @pytest.mark.asyncio
    async def test_resume_from_checkpoint_page(
        self,
        connector: ZohoConnector,
        base_credentials: dict[str, Any],
    ) -> None:
        calls: list[dict[str, Any]] = []

        async def fake_fetch(endpoint: str, *, access_token: str, base_url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
            assert params is not None
            calls.append(params)
            return {"invoices": [], "page_context": {"has_more_page": False}}

        with patch.object(connector, "_fetch", side_effect=fake_fetch):
            await connector.extract(
                DatasetType.INVOICE_REGISTER,
                credentials=base_credentials,
                checkpoint={"page": 3, "page_size": 50},
            )

        assert calls[0]["page"] == 3
        assert calls[0]["per_page"] == 50

    @pytest.mark.asyncio
    async def test_contact_type_vendor_customer(
        self,
        connector: ZohoConnector,
        base_credentials: dict[str, Any],
    ) -> None:
        params_seen: list[dict[str, Any]] = []

        async def fake_fetch(endpoint: str, *, access_token: str, base_url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
            assert params is not None
            params_seen.append(params)
            return {"contacts": [], "page_context": {"has_more_page": False}}

        with patch.object(connector, "_fetch", side_effect=fake_fetch):
            await connector.extract(DatasetType.VENDOR_MASTER, credentials=base_credentials)
            await connector.extract(DatasetType.CUSTOMER_MASTER, credentials=base_credentials)

        assert params_seen[0].get("contact_type") == "vendor"
        assert params_seen[1].get("contact_type") == "customer"

    @pytest.mark.asyncio
    async def test_legacy_wrappers_delegate(
        self,
        connector: ZohoConnector,
        base_credentials: dict[str, Any],
    ) -> None:
        async def fake_fetch(endpoint: str, *, access_token: str, base_url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
            if endpoint == "reports/trialbalance":
                return {"trialbalance": []}
            if endpoint == "reports/generalledger":
                return {"generalledger": []}
            return {}

        with patch.object(connector, "_fetch", side_effect=fake_fetch):
            tb = await connector.extract_trial_balance(credentials=base_credentials)
            gl = await connector.extract_general_ledger(credentials=base_credentials)

        assert tb["dataset_type"] == DatasetType.TRIAL_BALANCE.value
        assert gl["dataset_type"] == DatasetType.GENERAL_LEDGER.value


class TestZohoSecretResolution:
    @pytest.mark.asyncio
    async def test_resolve_creds_from_secret_ref(self, connector: ZohoConnector) -> None:
        with patch(
            "financeops.modules.erp_sync.infrastructure.connectors.zoho.secret_store.get_secret",
            new_callable=AsyncMock,
            return_value={
                "access_token": "secret-token",
                "organization_id": "org-secret",
            },
        ):
            creds, organization_id = await connector._resolve_creds({"secret_ref": "abc"})

        assert creds["access_token"] == "secret-token"
        assert organization_id == "org-secret"
