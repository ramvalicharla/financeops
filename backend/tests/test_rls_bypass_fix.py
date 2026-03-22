from __future__ import annotations

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from jose import jwt
from starlette.requests import Request

import financeops.api.deps as deps
from financeops.config import settings
from financeops.core.exceptions import AuthenticationError
from financeops.main import app


@pytest.mark.asyncio
async def test_missing_tenant_id_in_token_returns_401() -> None:
    """Route returns 401 when JWT has no tenant_id claim."""
    token = jwt.encode(
        {"sub": "00000000-0000-0000-0000-000000000001", "type": "access"},
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 401
    body = response.json()
    assert "data" not in body or not body.get("data")


@pytest.mark.asyncio
async def test_malformed_token_returns_401_not_data(monkeypatch: pytest.MonkeyPatch) -> None:
    """Malformed JWT never reaches DB layer."""

    class _SessionCtx:
        def __init__(self, session: AsyncMock) -> None:
            self._session = session

        async def __aenter__(self) -> AsyncMock:
            return self._session

        async def __aexit__(self, exc_type, exc, tb) -> bool:
            del exc_type, exc, tb
            return False

    fake_session = AsyncMock()
    fake_session.execute = AsyncMock()
    fake_session.rollback = AsyncMock()
    fake_session.close = AsyncMock()
    fake_session_local = AsyncMock(return_value=_SessionCtx(fake_session))

    monkeypatch.setattr(deps, "AsyncSessionLocal", fake_session_local)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid.token.value"},
        )

    assert response.status_code == 401
    fake_session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_empty_tenant_id_never_yields_unscoped_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """get_async_session raises before yielding if tenant_id empty."""
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "scheme": "http",
            "query_string": b"",
            "headers": [(b"authorization", b"Bearer x.y.z")],
            "client": ("127.0.0.1", 1234),
            "server": ("test", 80),
            "http_version": "1.1",
        }
    )
    request.state.tenant_id = ""

    monkeypatch.setattr(deps, "decode_token", lambda _token: {"sub": "abc", "tenant_id": ""})
    set_tenant_context = AsyncMock()
    monkeypatch.setattr(deps, "set_tenant_context", set_tenant_context)

    gen: AsyncGenerator = deps.get_async_session(request)
    with pytest.raises(AuthenticationError):
        await gen.__anext__()

    set_tenant_context.assert_not_awaited()
