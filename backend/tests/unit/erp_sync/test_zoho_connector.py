from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from financeops.modules.erp_sync.infrastructure.connectors.zoho import AuthenticationError, ZohoConnector


class _DummyResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict:
        return self._payload


class _DummyClient:
    def __init__(self, post_response: _DummyResponse | None = None, get_response: _DummyResponse | None = None):
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


@pytest.mark.asyncio
async def test_zoho_token_refresh_on_expiry(monkeypatch: pytest.MonkeyPatch) -> None:
    connector = ZohoConnector()
    creds = {
        "access_token": "expired",
        "refresh_token": "refresh",
        "client_id": "client",
        "client_secret": "secret",
        "token_expires_at": (datetime.now(UTC) - timedelta(minutes=1)).isoformat(),
    }

    monkeypatch.setattr(
        "financeops.modules.erp_sync.infrastructure.connectors.zoho.httpx.AsyncClient",
        lambda timeout=30.0: _DummyClient(post_response=_DummyResponse(200, {"access_token": "new-token", "expires_in": 3600})),
    )

    token = await connector._get_valid_token(creds)
    assert token == "new-token"
    assert creds["access_token"] == "new-token"


@pytest.mark.asyncio
async def test_zoho_trial_balance_extraction(monkeypatch: pytest.MonkeyPatch) -> None:
    connector = ZohoConnector()
    async def _token(creds: dict) -> str:
        return "token"
    monkeypatch.setattr(connector, "_get_valid_token", _token)

    async def fake_fetch(endpoint: str, *, access_token: str, base_url: str, params: dict | None = None) -> dict:
        assert endpoint == "reports/trialbalance"
        return {
            "trialbalance": [
                {"account_name": "Cash", "account_code": "1001", "closing_balance": "123.45"},
            ]
        }

    monkeypatch.setattr(connector, "_fetch", fake_fetch)

    result = await connector.extract_trial_balance(
        credentials={"organization_id": "org-1", "access_token": "token", "token_expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat()},
        from_date="2026-01-01",
        to_date="2026-01-31",
    )
    assert result["dataset_type"] == "trial_balance"
    assert len(result["records"]) == 1
    assert str(result["records"][0]["closing_balance"]) == "123.45"


@pytest.mark.asyncio
async def test_zoho_connection_test(monkeypatch: pytest.MonkeyPatch) -> None:
    connector = ZohoConnector()
    async def _token(creds: dict) -> str:
        return "token"
    monkeypatch.setattr(connector, "_get_valid_token", _token)

    async def fake_fetch(endpoint: str, *, access_token: str, base_url: str, params: dict | None = None) -> dict:
        assert endpoint == "organizations"
        return {"organizations": [{"organization_id": "org-1"}]}

    monkeypatch.setattr(connector, "_fetch", fake_fetch)
    payload = await connector.test_connection({"organization_id": "org-1", "access_token": "token"})
    assert payload["ok"] is True


@pytest.mark.asyncio
async def test_zoho_handles_auth_error(monkeypatch: pytest.MonkeyPatch) -> None:
    connector = ZohoConnector()

    monkeypatch.setattr(
        "financeops.modules.erp_sync.infrastructure.connectors.zoho.httpx.AsyncClient",
        lambda timeout=30.0: _DummyClient(get_response=_DummyResponse(401, {"message": "invalid token"})),
    )

    with pytest.raises(AuthenticationError):
        await connector._fetch("reports/trialbalance", access_token="bad", base_url=connector.ZOHO_API_BASE)
