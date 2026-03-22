from __future__ import annotations

import pytest

from financeops.security.antivirus import AntivirusUnavailableError, scan_file


class _FakeClient:
    def __init__(self, response: dict[str, tuple[str, str | None]]) -> None:
        self._response = response

    def instream(self, _stream) -> dict[str, tuple[str, str | None]]:
        return self._response


class _FakeClamdModule:
    def __init__(self, response: dict[str, tuple[str, str | None]], fail: bool = False) -> None:
        self._response = response
        self._fail = fail

    def ClamdUnixSocket(self, path: str):  # noqa: N802
        if self._fail:
            raise OSError(f"socket_unavailable:{path}")
        return _FakeClient(self._response)

    def ClamdNetworkSocket(self, host: str, port: int):  # noqa: N802
        if self._fail:
            raise OSError(f"tcp_unavailable:{host}:{port}")
        return _FakeClient(self._response)


@pytest.mark.asyncio
async def test_scan_file_returns_clean_when_scan_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "financeops.security.antivirus.clamd",
        _FakeClamdModule({"stream": ("OK", None)}),
    )
    monkeypatch.setattr("financeops.security.antivirus.settings.CLAMAV_REQUIRED", False)

    result = await scan_file(b"safe-data", "safe.csv")
    assert result.clean is True
    assert result.scanner == "clamav"
    assert result.threat_name is None


@pytest.mark.asyncio
async def test_scan_file_detects_infection(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "financeops.security.antivirus.clamd",
        _FakeClamdModule({"stream": ("FOUND", "Eicar-Test-Signature")}),
    )
    monkeypatch.setattr("financeops.security.antivirus.settings.CLAMAV_REQUIRED", False)

    result = await scan_file(b"infected-data", "infected.csv")
    assert result.clean is False
    assert result.scanner == "clamav"
    assert result.threat_name == "Eicar-Test-Signature"


@pytest.mark.asyncio
async def test_scan_file_unavailable_non_required_returns_clean(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(
        "financeops.security.antivirus.clamd",
        _FakeClamdModule({"stream": ("OK", None)}, fail=True),
    )
    monkeypatch.setattr("financeops.security.antivirus.settings.CLAMAV_REQUIRED", False)

    result = await scan_file(b"safe-data", "safe.csv")
    assert result.clean is True
    assert result.scanner == "disabled"
    assert "clamav_unavailable" in caplog.text


@pytest.mark.asyncio
async def test_scan_file_unavailable_required_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "financeops.security.antivirus.clamd",
        _FakeClamdModule({"stream": ("OK", None)}, fail=True),
    )
    monkeypatch.setattr("financeops.security.antivirus.settings.CLAMAV_REQUIRED", True)

    with pytest.raises(AntivirusUnavailableError):
        await scan_file(b"safe-data", "safe.csv")

