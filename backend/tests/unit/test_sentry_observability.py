from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from financeops.core.exceptions import unhandled_error_handler
from financeops.observability import sentry as sentry_module


def test_configure_sentry_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    init_mock = Mock()
    monkeypatch.setattr(sentry_module.sentry_sdk, "init", init_mock)
    monkeypatch.setattr(sentry_module, "_SENTRY_CONFIGURED", False)

    sentry_module.configure_sentry(
        dsn="https://examplePublicKey@o0.ingest.sentry.io/0",
        environment="test",
        release="test-release",
    )
    sentry_module.configure_sentry(
        dsn="https://examplePublicKey@o0.ingest.sentry.io/0",
        environment="test",
        release="test-release",
    )

    assert init_mock.call_count == 1


@pytest.mark.asyncio
async def test_unhandled_error_handler_captures_exception_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    capture_mock = Mock()
    monkeypatch.setattr("financeops.core.exceptions.sentry_sdk.capture_exception", capture_mock)

    request = SimpleNamespace(
        url=SimpleNamespace(path="/boom"),
        state=SimpleNamespace(request_id="req-1"),
    )
    exc = RuntimeError("boom")

    response = await unhandled_error_handler(request, exc)

    assert response.status_code == 500
    assert getattr(exc, "_sentry_reported", False) is True
    capture_mock.assert_called_once_with(exc)
