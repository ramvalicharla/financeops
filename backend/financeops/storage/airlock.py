from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import Literal

from financeops.config import settings
from financeops.security.antivirus import AntivirusUnavailableError, scan_file

log = logging.getLogger(__name__)

_ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # xlsx
    "application/vnd.ms-excel",  # xls
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # docx
    "text/csv",
    "text/plain",
    "application/json",
    "image/png",
    "image/jpeg",
}


def detect_mime_type(
    file_bytes: bytes,
    filename: str,
    *,
    fail_on_missing_magic: bool = False,
) -> str:
    """Detect MIME with libmagic; optionally fail closed when libmagic is unavailable."""
    try:
        import magic
    except ImportError:
        if fail_on_missing_magic:
            raise RuntimeError("libmagic unavailable")
        log.warning("python-magic not installed - falling back to filename extension")
        return _guess_mime_from_filename(filename)
    return str(magic.from_buffer(file_bytes[:4096], mime=True))


@dataclass
class AirlockResult:
    status: Literal["APPROVED", "REJECTED", "SCAN_SKIPPED"]
    sha256: str
    filename: str
    size_bytes: int
    mime_type: str
    scan_result: str
    rejection_reason: str | None = None


async def scan_and_seal(
    file_bytes: bytes,
    filename: str,
    tenant_id: str,
) -> AirlockResult:
    """
    5-step file ingestion safety layer:
    1. Validate file type via magic bytes
    2. Validate file size
    3. SHA256 hash
    4. ClamAV scan
    5. Return AirlockResult
    """
    # Step 1: Validate file type using python-magic
    mime_type = detect_mime_type(file_bytes, filename, fail_on_missing_magic=False)

    if mime_type not in _ALLOWED_MIME_TYPES:
        log.warning(
            "Airlock REJECTED: tenant=%s file=%s mime=%s",
            str(tenant_id)[:8],
            filename,
            mime_type,
        )
        return AirlockResult(
            status="REJECTED",
            sha256=hashlib.sha256(file_bytes).hexdigest(),
            filename=filename,
            size_bytes=len(file_bytes),
            mime_type=mime_type,
            scan_result="rejected",
            rejection_reason=f"File type '{mime_type}' is not permitted",
        )

    # Step 2: Validate file size
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(file_bytes) > max_bytes:
        return AirlockResult(
            status="REJECTED",
            sha256=hashlib.sha256(file_bytes).hexdigest(),
            filename=filename,
            size_bytes=len(file_bytes),
            mime_type=mime_type,
            scan_result="rejected",
            rejection_reason=f"File size {len(file_bytes)} exceeds limit {max_bytes}",
        )

    # Step 3: SHA256 hash
    sha256 = hashlib.sha256(file_bytes).hexdigest()

    # Step 4: ClamAV scan (fail-closed when required)
    try:
        av_result = await scan_file(file_bytes, filename)
    except AntivirusUnavailableError:
        if settings.CLAMAV_REQUIRED:
            return AirlockResult(
                status="REJECTED",
                sha256=sha256,
                filename=filename,
                size_bytes=len(file_bytes),
                mime_type=mime_type,
                scan_result="rejected",
                rejection_reason=(
                    "AV scan could not complete and CLAMAV_REQUIRED=True. "
                    "File rejected. Check ClamAV service health."
                ),
            )
        log.warning(
            "ClamAV unavailable - scan skipped (CLAMAV_REQUIRED=False) tenant=%s",
            str(tenant_id)[:8],
        )
        return AirlockResult(
            status="SCAN_SKIPPED",
            sha256=sha256,
            filename=filename,
            size_bytes=len(file_bytes),
            mime_type=mime_type,
            scan_result="scan_skipped",
            rejection_reason=None,
        )

    if not av_result.clean:
        log.critical(
            "Malicious file detected - rejecting upload tenant=%s filename=%s threat=%s",
            str(tenant_id)[:8],
            filename,
            av_result.threat_name,
        )
        return AirlockResult(
            status="REJECTED",
            sha256=sha256,
            filename=filename,
            size_bytes=len(file_bytes),
            mime_type=mime_type,
            scan_result="rejected",
            rejection_reason=f"File rejected: malware detected ({av_result.threat_name})",
        )

    if av_result.scanner != "clamav":
        if settings.CLAMAV_REQUIRED:
            return AirlockResult(
                status="REJECTED",
                sha256=sha256,
                filename=filename,
                size_bytes=len(file_bytes),
                mime_type=mime_type,
                scan_result="rejected",
                rejection_reason=(
                    "AV scan could not complete and CLAMAV_REQUIRED=True. "
                    "File rejected. Check ClamAV service health."
                ),
            )
        log.warning(
            "ClamAV unavailable - scan skipped (CLAMAV_REQUIRED=False) tenant=%s",
            str(tenant_id)[:8],
        )
        return AirlockResult(
            status="SCAN_SKIPPED",
            sha256=sha256,
            filename=filename,
            size_bytes=len(file_bytes),
            mime_type=mime_type,
            scan_result="scan_skipped",
            rejection_reason=None,
        )

    log.info(
        "Airlock APPROVED: tenant=%s file=%s size=%d sha256=%s",
        str(tenant_id)[:8],
        filename,
        len(file_bytes),
        sha256[:12],
    )
    return AirlockResult(
        status="APPROVED",
        sha256=sha256,
        filename=filename,
        size_bytes=len(file_bytes),
        mime_type=mime_type,
        scan_result="clean",
        rejection_reason=None,
    )


def _guess_mime_from_filename(filename: str) -> str:
    """Fallback MIME type detection from file extension."""
    ext_map = {
        ".pdf": "application/pdf",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xls": "application/vnd.ms-excel",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".csv": "text/csv",
        ".txt": "text/plain",
        ".json": "application/json",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
    }
    for ext, mime in ext_map.items():
        if filename.lower().endswith(ext):
            return mime
    return "application/octet-stream"
