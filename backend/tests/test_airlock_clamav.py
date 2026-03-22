from __future__ import annotations

import pytest

import financeops.storage.airlock as airlock
from financeops.security.antivirus import AntivirusResult, AntivirusUnavailableError


@pytest.mark.asyncio
async def test_eicar_file_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """EICAR test string is rejected."""
    monkeypatch.setattr(airlock, "detect_mime_type", lambda *_args, **_kwargs: "text/csv")

    async def _infected_scan(_content: bytes, _filename: str) -> AntivirusResult:
        return AntivirusResult(
            clean=False,
            threat_name="Eicar-Test-Signature",
            scanner="clamav",
        )

    monkeypatch.setattr(airlock, "scan_file", _infected_scan)

    eicar = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
    result = await airlock.scan_and_seal(eicar, "eicar.csv", "tenant-1")

    assert result.status == "REJECTED"
    assert result.rejection_reason is not None
    assert "malware" in result.rejection_reason.lower()


@pytest.mark.asyncio
async def test_clamav_unavailable_required_true_rejects_upload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CLAMAV_REQUIRED=True blocks upload when ClamAV is down."""
    monkeypatch.setattr(airlock, "detect_mime_type", lambda *_args, **_kwargs: "text/csv")
    monkeypatch.setattr(airlock.settings, "CLAMAV_REQUIRED", True)

    async def _unavailable_scan(_content: bytes, _filename: str) -> AntivirusResult:
        raise AntivirusUnavailableError("clamav_unavailable")

    monkeypatch.setattr(airlock, "scan_file", _unavailable_scan)

    result = await airlock.scan_and_seal(b"id,value\n1,2", "sample.csv", "tenant-1")

    assert result.status == "REJECTED"
    assert result.rejection_reason is not None
    assert "CLAMAV_REQUIRED" in result.rejection_reason


@pytest.mark.asyncio
async def test_clamav_unavailable_required_false_allows_upload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CLAMAV_REQUIRED=False allows upload when ClamAV is down."""
    monkeypatch.setattr(airlock, "detect_mime_type", lambda *_args, **_kwargs: "text/csv")
    monkeypatch.setattr(airlock.settings, "CLAMAV_REQUIRED", False)

    async def _unavailable_scan(_content: bytes, _filename: str) -> AntivirusResult:
        raise AntivirusUnavailableError("clamav_unavailable")

    monkeypatch.setattr(airlock, "scan_file", _unavailable_scan)

    result = await airlock.scan_and_seal(b"id,value\n1,2", "sample.csv", "tenant-1")

    assert result.status == "SCAN_SKIPPED"


@pytest.mark.asyncio
async def test_clean_file_passes_all_airlock_stages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Clean file passes every airlock stage end-to-end."""
    monkeypatch.setattr(airlock, "detect_mime_type", lambda *_args, **_kwargs: "text/csv")

    async def _clean_scan(_content: bytes, _filename: str) -> AntivirusResult:
        return AntivirusResult(clean=True, threat_name=None, scanner="clamav")

    monkeypatch.setattr(airlock, "scan_file", _clean_scan)

    result = await airlock.scan_and_seal(b"id,value\n1,2", "sample.csv", "tenant-1")

    assert result.status == "APPROVED"
    assert result.scan_result == "clean"
