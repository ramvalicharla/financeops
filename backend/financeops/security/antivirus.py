from __future__ import annotations

import asyncio
import io
import logging
from dataclasses import dataclass
from typing import Any

from financeops.config import settings

try:
    import clamd
except Exception:  # pragma: no cover - exercised through availability tests
    clamd = None

log = logging.getLogger(__name__)


@dataclass
class AntivirusResult:
    clean: bool
    threat_name: str | None
    scanner: str  # "clamav" or "disabled"


class AntivirusUnavailableError(Exception):
    pass


def _parse_scan_response(scan_response: Any) -> tuple[bool, str | None]:
    if isinstance(scan_response, dict) and scan_response:
        value = next(iter(scan_response.values()))
        if isinstance(value, tuple) and len(value) >= 1:
            status = str(value[0]).upper()
            threat = str(value[1]) if len(value) > 1 and value[1] else None
            if status == "FOUND":
                return False, threat
            if status == "OK":
                return True, None
    return True, None


def _scan_with_client(client: Any, content: bytes) -> tuple[bool, str | None]:
    response = client.instream(io.BytesIO(content))
    return _parse_scan_response(response)


async def scan_file(content: bytes, filename: str) -> AntivirusResult:
    """
    Scan file bytes with ClamAV over unix socket with TCP fallback.
    """
    if clamd is None:
        if settings.CLAMAV_REQUIRED:
            raise AntivirusUnavailableError("clamd_library_unavailable")
        log.warning("clamav_unavailable scanner=disabled filename=%s", filename)
        return AntivirusResult(clean=True, threat_name=None, scanner="disabled")

    clients = [
        lambda: clamd.ClamdUnixSocket(path=settings.CLAMAV_SOCKET),
        lambda: clamd.ClamdNetworkSocket(host=settings.CLAMAV_HOST, port=settings.CLAMAV_PORT),
    ]

    last_error: Exception | None = None
    for client_factory in clients:
        try:
            client = await asyncio.wait_for(asyncio.to_thread(client_factory), timeout=30.0)
            clean, threat_name = await asyncio.wait_for(
                asyncio.to_thread(_scan_with_client, client, content),
                timeout=30.0,
            )
            if clean:
                return AntivirusResult(clean=True, threat_name=None, scanner="clamav")
            log.critical(
                "malware_detected filename=%s threat_name=%s",
                filename,
                threat_name,
            )
            return AntivirusResult(clean=False, threat_name=threat_name, scanner="clamav")
        except Exception as exc:  # pragma: no cover - exercised through mocks
            last_error = exc
            continue

    if settings.CLAMAV_REQUIRED:
        raise AntivirusUnavailableError("clamav_unavailable") from last_error

    log.warning("clamav_unavailable scanner=disabled filename=%s", filename)
    return AntivirusResult(clean=True, threat_name=None, scanner="disabled")

