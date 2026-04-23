from __future__ import annotations

import ssl

import pytest

from financeops.db import session as session_module


def test_build_ssl_context_disables_verification_outside_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(session_module.settings, "APP_ENV", "development")

    context = session_module._build_ssl_context()

    assert context.check_hostname is False
    assert context.verify_mode == ssl.CERT_NONE


def test_build_ssl_context_disables_verification_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(session_module.settings, "APP_ENV", "production")

    context = session_module._build_ssl_context()

    assert context.check_hostname is False
    assert context.verify_mode == ssl.CERT_NONE


def test_build_ssl_context_sets_insecure_flags_even_with_custom_factory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeSSLContext:
        def __init__(self) -> None:
            self.check_hostname = True
            self.verify_mode = ssl.CERT_REQUIRED

        def __setattr__(self, name, value) -> None:
            object.__setattr__(self, name, value)

    monkeypatch.setattr(session_module.settings, "APP_ENV", "production")
    monkeypatch.setattr(session_module.ssl, "create_default_context", lambda: FakeSSLContext())

    context = session_module._build_ssl_context()

    assert context.check_hostname is False
    assert context.verify_mode == ssl.CERT_NONE
