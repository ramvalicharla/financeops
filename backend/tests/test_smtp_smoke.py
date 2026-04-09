from __future__ import annotations

import pytest

from financeops.config import Settings, settings
from financeops.modules.scheduled_delivery.application.delivery_service import (
    DeliveryService,
    _assert_smtp_configured,
)


def _set_smtp(
    monkeypatch: pytest.MonkeyPatch,
    *,
    required: bool,
    host: str,
    user: str,
    password: str,
    port: int = 587,
) -> None:
    monkeypatch.setattr(settings, "SMTP_REQUIRED", required, raising=False)
    monkeypatch.setattr(settings, "SMTP_HOST", host, raising=False)
    monkeypatch.setattr(settings, "SMTP_USER", user, raising=False)
    monkeypatch.setattr(settings, "SMTP_PASSWORD", password, raising=False)
    monkeypatch.setattr(settings, "SMTP_PORT", port, raising=False)


def _email_payload() -> dict[str, object]:
    return {
        "recipient": "ops@example.com",
        "subject": "Smoke test",
        "body": "hello",
        "attachment": b"payload",
        "filename": "smoke.pdf",
    }


def test_smtp_required_default_is_false() -> None:
    """Settings default keeps SMTP fail-open unless explicitly enabled."""
    assert Settings.model_fields["SMTP_REQUIRED"].default is False


def test_smtp_required_true_with_valid_config_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Required SMTP with real host/user/password passes guard checks."""
    _set_smtp(
        monkeypatch,
        required=True,
        host="mail.example.com",
        user="user@example.com",
        password="secret",
    )
    _assert_smtp_configured()


def test_smtp_required_true_missing_host_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """Required SMTP rejects localhost/default host as unconfigured."""
    _set_smtp(
        monkeypatch,
        required=True,
        host="localhost",
        user="user",
        password="pass",
    )

    with pytest.raises(RuntimeError, match="SMTP_HOST"):
        _assert_smtp_configured()


def test_smtp_required_true_missing_user_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """Required SMTP rejects blank SMTP_USER."""
    _set_smtp(
        monkeypatch,
        required=True,
        host="mail.example.com",
        user="",
        password="pass",
    )

    with pytest.raises(RuntimeError, match="SMTP_USER"):
        _assert_smtp_configured()


def test_smtp_required_true_missing_password_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """Required SMTP rejects blank SMTP_PASSWORD."""
    _set_smtp(
        monkeypatch,
        required=True,
        host="mail.example.com",
        user="user@example.com",
        password="",
    )

    with pytest.raises(RuntimeError, match="SMTP_PASSWORD"):
        _assert_smtp_configured()


def test_smtp_required_false_skips_check(monkeypatch: pytest.MonkeyPatch) -> None:
    """When SMTP_REQUIRED is false, missing SMTP config is tolerated."""
    _set_smtp(
        monkeypatch,
        required=False,
        host="",
        user="",
        password="",
    )
    _assert_smtp_configured()


def test_smtp_required_true_all_missing_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """Required SMTP reports all missing fields in one actionable error."""
    _set_smtp(
        monkeypatch,
        required=True,
        host="",
        user="",
        password="",
    )

    with pytest.raises(RuntimeError) as exc:
        _assert_smtp_configured()

    message = str(exc.value)
    assert "SMTP_HOST" in message
    assert "SMTP_USER" in message
    assert "SMTP_PASSWORD" in message


@pytest.mark.asyncio
async def test_email_delivery_fails_loudly_when_smtp_required_not_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Email dispatch raises RuntimeError immediately when required SMTP is missing."""
    _set_smtp(
        monkeypatch,
        required=True,
        host="localhost",
        user="",
        password="",
    )

    service = DeliveryService()
    with pytest.raises(RuntimeError, match="SMTP_REQUIRED=True"):
        await service._dispatch_email(**_email_payload())


@pytest.mark.asyncio
async def test_email_delivery_succeeds_when_smtp_not_required(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Email dispatch remains fail-open when SMTP_REQUIRED is false."""
    _set_smtp(
        monkeypatch,
        required=False,
        host="",
        user="",
        password="",
    )

    async def fake_send(*args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        raise OSError("smtp unavailable")

    from financeops.modules.scheduled_delivery.application import delivery_service as module

    monkeypatch.setattr(module, "send_smtp_message", fake_send)

    service = DeliveryService()
    await service._dispatch_email(**_email_payload())


@pytest.mark.asyncio
async def test_email_delivery_guard_fires_before_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SMTP guard runs before any SMTP connection attempt or thread dispatch."""
    _set_smtp(
        monkeypatch,
        required=True,
        host="localhost",
        user="",
        password="",
    )

    from financeops.modules.scheduled_delivery.application import delivery_service as module

    send_called = {"value": False}

    async def fake_send(*args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        send_called["value"] = True

    monkeypatch.setattr(module, "send_smtp_message", fake_send)

    service = DeliveryService()
    with pytest.raises(RuntimeError):
        await service._dispatch_email(**_email_payload())

    assert send_called["value"] is False


def test_smtp_error_message_is_actionable(monkeypatch: pytest.MonkeyPatch) -> None:
    """Guard error message contains both enable and disable remediation hints."""
    _set_smtp(
        monkeypatch,
        required=True,
        host="",
        user="",
        password="",
    )

    with pytest.raises(RuntimeError) as exc:
        _assert_smtp_configured()

    message = str(exc.value)
    assert "SMTP_REQUIRED=True" in message
    assert "SMTP_REQUIRED=False" in message


def test_smtp_required_env_var_is_boolean() -> None:
    """Runtime settings expose SMTP_REQUIRED as boolean, not string."""
    assert isinstance(settings.SMTP_REQUIRED, bool)
