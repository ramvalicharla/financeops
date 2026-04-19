from __future__ import annotations

import ssl

import pytest

from financeops.db import session as session_module


def test_build_ssl_context_relaxes_verification_outside_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(session_module.settings, "APP_ENV", "development")

    context = session_module._build_ssl_context()

    assert context.check_hostname is False
    assert context.verify_mode == ssl.CERT_NONE


def test_build_ssl_context_enforces_verification_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(session_module.settings, "APP_ENV", "production")

    context = session_module._build_ssl_context()

    assert context.check_hostname is True
    assert context.verify_mode == ssl.CERT_REQUIRED


def test_build_ssl_context_fails_fast_if_production_context_stays_insecure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeSSLContext:
        def __init__(self) -> None:
            self.check_hostname = False
            self.verify_mode = ssl.CERT_NONE

        def __setattr__(self, name, value) -> None:
            if name == "check_hostname":
                object.__setattr__(self, name, False)
                return
            if name == "verify_mode":
                object.__setattr__(self, name, ssl.CERT_NONE)
                return
            object.__setattr__(self, name, value)

    monkeypatch.setattr(session_module.settings, "APP_ENV", "production")
    monkeypatch.setattr(session_module.ssl, "create_default_context", lambda: FakeSSLContext())

    with pytest.raises(RuntimeError, match="Production database TLS must enforce hostname and certificate verification"):
        session_module._build_ssl_context()
