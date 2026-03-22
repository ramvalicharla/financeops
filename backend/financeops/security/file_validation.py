from __future__ import annotations

from pathlib import Path

from financeops.config import settings
from financeops.storage.airlock import detect_mime_type

ALLOWED_MIME_TYPES = {
    "text/csv",
    "text/plain",
    "application/json",
    "application/xml",
    "text/xml",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
}

ALLOWED_EXTENSIONS = {".csv", ".json", ".xml", ".xlsx", ".xls"}
MAX_FILE_SIZE_BYTES = 52_428_800  # 50MB

_EXTENSION_MIME_MAP: dict[str, set[str]] = {
    ".csv": {"text/csv", "text/plain"},
    ".json": {"application/json", "text/plain"},
    ".xml": {"application/xml", "text/xml"},
    ".xlsx": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
    ".xls": {"application/vnd.ms-excel"},
}


class FileValidationError(Exception):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def validate_file(filename: str, content: bytes, max_size: int | None = None) -> None:
    """
    Validate uploaded file and raise FileValidationError on any failure.
    """
    if not filename:
        raise FileValidationError("filename_required")
    if ".." in filename or "/" in filename or "\\" in filename:
        raise FileValidationError("invalid_filename_path_traversal")
    if not isinstance(content, (bytes, bytearray)) or len(content) == 0:
        raise FileValidationError("empty_file")

    max_size_bytes = max_size or settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(content) > max_size_bytes:
        raise FileValidationError("file_too_large")

    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise FileValidationError("unsupported_extension")

    try:
        mime_type = detect_mime_type(
            bytes(content),
            filename,
            fail_on_missing_magic=True,
        )
    except Exception as exc:
        raise FileValidationError("libmagic_unavailable") from exc

    if mime_type not in ALLOWED_MIME_TYPES:
        raise FileValidationError("unsupported_mime_type")

    allowed_for_extension = _EXTENSION_MIME_MAP.get(extension, set())
    if mime_type not in allowed_for_extension:
        raise FileValidationError("extension_mime_mismatch")

