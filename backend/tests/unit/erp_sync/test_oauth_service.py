from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from financeops.core.exceptions import AuthenticationError, AuthorizationError, ValidationError
from financeops.modules.erp_sync.application.oauth_service import (
    _resolve_provider,
    consume_oauth_callback,
    get_decrypted_access_token,
    refresh_connection_token,
    start_oauth_session,
)


def _scalar_result(value):
    return SimpleNamespace(scalar_one_or_none=lambda: value)


def _connection(*, connector_type: str = "zoho", tenant_id: uuid.UUID | None = None):
    return SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=tenant_id or uuid.uuid4(),
        connector_type=connector_type,
        secret_ref="enc-secret-ref",
        created_by=uuid.uuid4(),
        token_expires_at=None,
        token_refreshed_at=None,
        oauth_scopes=None,
    )


def _oauth_session(*, tenant_id: uuid.UUID, connection_id: uuid.UUID, status: str = "PENDING"):
    return SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        connection_id=connection_id,
        provider="ZOHO",
        state_token="state-token",
        status=status,
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
        consumed_at=None,
        redirect_uri="https://app.example.com/oauth/callback",
        code_verifier_enc="enc-verifier",
        scopes="ZohoBooks.fullaccess.all",
        encrypted_tokens=None,
        token_expires_at=None,
    )


class _DummyResponse:
    def __init__(self, status_code: int, payload: dict[str, object]):
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict[str, object]:
        return self._payload


class _DummyClient:
    def __init__(self, response: _DummyResponse):
        self._response = response

    async def __aenter__(self) -> "_DummyClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def post(self, *args, **kwargs) -> _DummyResponse:
        return self._response


def test_resolve_provider_mappings() -> None:
    assert _resolve_provider("zoho") == "ZOHO"
    assert _resolve_provider("quickbooks") == "QBO"


def test_resolve_provider_unsupported_raises() -> None:
    with pytest.raises(ValidationError):
        _resolve_provider("tally")


@pytest.mark.asyncio
async def test_start_oauth_session_returns_authorization_url() -> None:
    tenant_id = uuid.uuid4()
    connection = _connection(connector_type="zoho", tenant_id=tenant_id)
    session = AsyncMock()
    session.add = MagicMock()

    with (
        patch(
            "financeops.modules.erp_sync.application.oauth_service._get_connection",
            new_callable=AsyncMock,
            return_value=connection,
        ),
        patch(
            "financeops.modules.erp_sync.application.oauth_service._resolve_credentials",
            new_callable=AsyncMock,
            return_value=({"client_id": "cid"}, "enc-ref", None),
        ),
        patch(
            "financeops.modules.erp_sync.application.oauth_service._expire_pending_sessions",
            new_callable=AsyncMock,
        ),
        patch(
            "financeops.modules.erp_sync.application.oauth_service.encrypt_field",
            return_value="encrypted-verifier",
        ),
    ):
        result = await start_oauth_session(
            session,
            tenant_id=tenant_id,
            connection_id=connection.id,
            entity_id=None,
            redirect_uri="https://app.example.com/oauth/callback",
            initiated_by_user_id=uuid.uuid4(),
        )

    assert "accounts.zoho.in" in result["authorization_url"]
    assert "code_challenge_method=S256" in result["authorization_url"]
    assert result["state_token"]


@pytest.mark.asyncio
async def test_consume_oauth_callback_replay_blocked() -> None:
    tenant_id = uuid.uuid4()
    connection_id = uuid.uuid4()
    oauth_session = _oauth_session(
        tenant_id=tenant_id,
        connection_id=connection_id,
        status="CONSUMED",
    )
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_scalar_result(oauth_session))

    with pytest.raises(AuthorizationError):
        await consume_oauth_callback(
            session,
            tenant_id=tenant_id,
            connection_id=connection_id,
            state_token="state-token",
            code="auth-code",
            initiated_by_user_id=uuid.uuid4(),
        )


@pytest.mark.asyncio
async def test_refresh_connection_token_missing_refresh_token() -> None:
    tenant_id = uuid.uuid4()
    connection = _connection(connector_type="zoho", tenant_id=tenant_id)
    session = AsyncMock()

    with (
        patch(
            "financeops.modules.erp_sync.application.oauth_service._get_connection",
            new_callable=AsyncMock,
            return_value=connection,
        ),
        patch(
            "financeops.modules.erp_sync.application.oauth_service._resolve_credentials",
            new_callable=AsyncMock,
            return_value=(
                {"client_id": "cid", "client_secret": "secret", "refresh_token": None},
                "enc-ref",
                None,
            ),
        ),
    ):
        with pytest.raises(AuthenticationError):
            await refresh_connection_token(
                session,
                tenant_id=tenant_id,
                connection_id=connection.id,
            )


@pytest.mark.asyncio
async def test_get_decrypted_access_token_auto_refreshes() -> None:
    tenant_id = uuid.uuid4()
    connection = _connection(connector_type="zoho", tenant_id=tenant_id)
    session = AsyncMock()

    expiring = (datetime.now(UTC) + timedelta(minutes=2)).isoformat()

    with (
        patch(
            "financeops.modules.erp_sync.application.oauth_service._get_connection",
            new_callable=AsyncMock,
            return_value=connection,
        ),
        patch(
            "financeops.modules.erp_sync.application.oauth_service._resolve_credentials",
            new_callable=AsyncMock,
            side_effect=[
                ({"access_token": "old", "token_expires_at": expiring}, "enc-ref", None),
                ({"access_token": "new", "token_expires_at": expiring}, "enc-ref", None),
            ],
        ),
        patch(
            "financeops.modules.erp_sync.application.oauth_service.refresh_connection_token",
            new_callable=AsyncMock,
        ) as mock_refresh,
    ):
        token = await get_decrypted_access_token(
            session,
            tenant_id=tenant_id,
            connection_id=connection.id,
            auto_refresh=True,
        )

    mock_refresh.assert_awaited_once()
    assert token == "new"


@pytest.mark.asyncio
async def test_consume_oauth_callback_persists_organization_id_and_appends_connection_secret_version() -> None:
    tenant_id = uuid.uuid4()
    connection = _connection(connector_type="zoho", tenant_id=tenant_id)
    session = AsyncMock()
    session.execute = AsyncMock(
        return_value=_scalar_result(_oauth_session(tenant_id=tenant_id, connection_id=connection.id))
    )

    with (
        patch(
            "financeops.modules.erp_sync.application.oauth_service._get_connection",
            new_callable=AsyncMock,
            return_value=connection,
        ),
        patch(
            "financeops.modules.erp_sync.application.oauth_service._resolve_credentials",
            new_callable=AsyncMock,
            return_value=(
                {
                    "client_id": "cid",
                    "client_secret": "secret",
                    "organization_id": "org-existing",
                    "use_sandbox": True,
                },
                "enc-old",
                None,
            ),
        ),
        patch(
            "financeops.modules.erp_sync.application.oauth_service.decrypt_field",
            return_value="verifier",
        ),
        patch(
            "financeops.modules.erp_sync.application.oauth_service.secret_store.put_secret",
            new_callable=AsyncMock,
            return_value="enc-new",
        ) as mock_put_secret,
        patch(
            "financeops.modules.erp_sync.application.oauth_service._append_connection_secret_version",
            new_callable=AsyncMock,
        ) as mock_append_version,
        patch(
            "financeops.modules.erp_sync.application.oauth_service.httpx.AsyncClient",
            return_value=_DummyClient(
                _DummyResponse(
                    200,
                    {"access_token": "new-access", "refresh_token": "new-refresh", "expires_in": 3600},
                )
            ),
        ),
    ):
        result = await consume_oauth_callback(
            session,
            tenant_id=tenant_id,
            connection_id=connection.id,
            state_token="state-token",
            code="auth-code",
            initiated_by_user_id=uuid.uuid4(),
            organization_id="org-callback",
        )

    updates = mock_put_secret.await_args.args[1]
    assert updates["organization_id"] == "org-callback"
    assert updates["use_sandbox"] is True
    assert mock_append_version.await_args.kwargs["secret_ref"] == "enc-new"
    assert mock_append_version.await_args.kwargs["scopes"] == "ZohoBooks.fullaccess.all"
    assert mock_append_version.await_args.kwargs["token_expires_at"] is not None
    assert result["status"] == "connected"


@pytest.mark.asyncio
async def test_refresh_connection_token_preserves_organization_id_and_appends_connection_secret_version() -> None:
    tenant_id = uuid.uuid4()
    connection = _connection(connector_type="zoho", tenant_id=tenant_id)
    session = AsyncMock()

    with (
        patch(
            "financeops.modules.erp_sync.application.oauth_service._get_connection",
            new_callable=AsyncMock,
            return_value=connection,
        ),
        patch(
            "financeops.modules.erp_sync.application.oauth_service._resolve_credentials",
            new_callable=AsyncMock,
            return_value=(
                {
                    "client_id": "cid",
                    "client_secret": "secret",
                    "refresh_token": "refresh-1",
                    "organization_id": "org-stored",
                    "realm_id": "realm-1",
                    "use_sandbox": True,
                },
                "enc-old",
                None,
            ),
        ),
        patch(
            "financeops.modules.erp_sync.application.oauth_service.secret_store.put_secret",
            new_callable=AsyncMock,
            return_value="enc-new",
        ) as mock_put_secret,
        patch(
            "financeops.modules.erp_sync.application.oauth_service._append_connection_secret_version",
            new_callable=AsyncMock,
        ) as mock_append_version,
        patch(
            "financeops.modules.erp_sync.application.oauth_service.httpx.AsyncClient",
            return_value=_DummyClient(
                _DummyResponse(
                    200,
                    {"access_token": "refreshed-access", "expires_in": 3600},
                )
            ),
        ),
    ):
        result = await refresh_connection_token(
            session,
            tenant_id=tenant_id,
            connection_id=connection.id,
            initiated_by_user_id=uuid.uuid4(),
        )

    updates = mock_put_secret.await_args.args[1]
    assert updates["organization_id"] == "org-stored"
    assert updates["realm_id"] == "realm-1"
    assert updates["use_sandbox"] is True
    assert mock_append_version.await_args.kwargs["secret_ref"] == "enc-new"
    assert mock_append_version.await_args.kwargs["token_expires_at"] is not None
    assert result["status"] == "refreshed"
