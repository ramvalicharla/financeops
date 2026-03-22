from __future__ import annotations

import uuid
from unittest.mock import Mock

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_internal_error_does_not_leak_exception_message(
    async_client: AsyncClient,
    test_access_token: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """500 responses return stable internal_error and never leak raw exception strings."""
    from financeops.modules.secret_rotation.api import routes as secret_routes

    async def _boom(**kwargs):  # type: ignore[no-untyped-def]
        _ = kwargs
        raise Exception("internal error: postgresql://user:secret@host/db")

    monkeypatch.setattr(secret_routes, "rotate_webhook_secret", _boom)
    response = await async_client.post(
        f"/api/v1/secrets/rotate/webhook/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 500
    body_text = response.text.lower()
    assert "postgresql" not in body_text
    assert "secret" not in body_text
    payload = response.json()
    error_message = payload.get("error", {}).get("message", "")
    assert "internal_error" in error_message


@pytest.mark.asyncio
async def test_exception_is_logged_not_leaked(
    async_client: AsyncClient,
    test_access_token: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exceptions are captured via logger.exception and not surfaced in API payloads."""
    from financeops.modules.secret_rotation.api import routes as secret_routes

    async def _boom(**kwargs):  # type: ignore[no-untyped-def]
        _ = kwargs
        raise Exception("secret data")

    log_exception = Mock()
    monkeypatch.setattr(secret_routes, "rotate_webhook_secret", _boom)
    monkeypatch.setattr(secret_routes.log, "exception", log_exception)

    response = await async_client.post(
        f"/api/v1/secrets/rotate/webhook/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 500
    assert log_exception.called
    assert "secret data" not in response.text.lower()
