from __future__ import annotations

import base64
import secrets

import pytest
from pydantic import ValidationError

from financeops.config import Settings, get_settings


def _set_required_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://financeops_test:testpassword@localhost:5433/financeops_test",
    )
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6380/0")
    monkeypatch.setenv("SECRET_KEY", "s" * 32)


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    get_settings.cache_clear()
    try:
        yield
    finally:
        get_settings.cache_clear()


def test_invalid_base64_encryption_key_raises_at_settings_load(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bad base64 FIELD_ENCRYPTION_KEY raises ValidationError at import."""
    _set_required_env(monkeypatch)
    monkeypatch.setenv("FIELD_ENCRYPTION_KEY", "not!!valid!!base64")
    monkeypatch.setenv("JWT_SECRET", "j" * 32)

    with pytest.raises(ValidationError) as exc:
        Settings()

    assert "FIELD_ENCRYPTION_KEY" in str(exc.value)


def test_wrong_length_encryption_key_raises_at_settings_load(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """16-byte key raises ValidationError - must be 32 bytes."""
    _set_required_env(monkeypatch)
    short_key = base64.urlsafe_b64encode(secrets.token_bytes(16)).decode()
    monkeypatch.setenv("FIELD_ENCRYPTION_KEY", short_key)
    monkeypatch.setenv("JWT_SECRET", "j" * 32)

    with pytest.raises(ValidationError) as exc:
        Settings()

    assert "32 bytes" in str(exc.value)


def test_valid_32_byte_key_passes_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Correctly generated 32-byte key passes without error."""
    _set_required_env(monkeypatch)
    good_key = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
    monkeypatch.setenv("FIELD_ENCRYPTION_KEY", good_key)
    monkeypatch.setenv("JWT_SECRET", "j" * 32)

    loaded = get_settings()
    assert loaded.FIELD_ENCRYPTION_KEY == good_key


def test_short_jwt_secret_raises_at_settings_load(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """JWT_SECRET under 32 chars raises ValidationError."""
    _set_required_env(monkeypatch)
    good_key = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
    monkeypatch.setenv("FIELD_ENCRYPTION_KEY", good_key)
    monkeypatch.setenv("JWT_SECRET", "tooshort")

    with pytest.raises(ValidationError) as exc:
        Settings()

    assert "32 characters" in str(exc.value)
