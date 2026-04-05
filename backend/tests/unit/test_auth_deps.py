from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import pytest
from fastapi import Request

from financeops.api import deps
from financeops.core.exceptions import AuthenticationError


def _make_request(path: str, authorization: str | None = None) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if authorization:
        headers.append((b"authorization", authorization.encode("utf-8")))
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": path,
            "headers": headers,
            "state": {},
        }
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/auth/accept-invite",
        "/api/v1/auth/mfa/verify",
        "/api/v1/auth/logout",
    ],
)
async def test_get_async_session_bypasses_tenant_context_for_bootstrap_auth_routes(
    monkeypatch: pytest.MonkeyPatch,
    path: str,
) -> None:
    session = type(
        "DummySession",
        (),
        {
            "flush": AsyncMock(),
            "rollback": AsyncMock(),
            "close": AsyncMock(),
        },
    )()

    @asynccontextmanager
    async def fake_session_local():
        yield session

    monkeypatch.setattr(deps, "AsyncSessionLocal", fake_session_local)

    generator = deps.get_async_session(_make_request(path))
    yielded = await anext(generator)
    assert yielded is session

    with pytest.raises(StopAsyncIteration):
        await anext(generator)

    session.flush.assert_awaited_once()
    session.close.assert_awaited_once()
    session.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_async_session_requires_tenant_context_for_non_public_paths() -> None:
    generator = deps.get_async_session(_make_request("/api/v1/auth/me"))

    with pytest.raises(AuthenticationError, match="tenant_id missing from token"):
        await anext(generator)
