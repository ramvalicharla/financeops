from __future__ import annotations

import pytest

from financeops.config import settings
from financeops.security.file_validation import FileValidationError, validate_file


def test_validate_file_allows_valid_csv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "financeops.security.file_validation.detect_mime_type",
        lambda *_args, **_kwargs: "text/csv",
    )
    validate_file("trial_balance.csv", b"account,amount\nA100,100.00\n")


def test_validate_file_allows_valid_xlsx(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "financeops.security.file_validation.detect_mime_type",
        lambda *_args, **_kwargs: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    validate_file("report.xlsx", b"PK\x03\x04sample")


def test_validate_file_rejects_file_over_50mb(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "financeops.security.file_validation.detect_mime_type",
        lambda *_args, **_kwargs: "text/csv",
    )
    oversized = b"a" * ((settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024) + 1)
    with pytest.raises(FileValidationError, match="file_too_large"):
        validate_file("large.csv", oversized)


def test_validate_file_rejects_disallowed_extension() -> None:
    with pytest.raises(FileValidationError, match="unsupported_extension"):
        validate_file("payload.exe", b"MZ")


def test_validate_file_rejects_mime_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "financeops.security.file_validation.detect_mime_type",
        lambda *_args, **_kwargs: "application/json",
    )
    with pytest.raises(FileValidationError, match="extension_mime_mismatch"):
        validate_file("records.csv", b'{"a": 1}')


def test_validate_file_rejects_empty_file() -> None:
    with pytest.raises(FileValidationError, match="empty_file"):
        validate_file("empty.csv", b"")


def test_validate_file_rejects_path_traversal_filename() -> None:
    with pytest.raises(FileValidationError, match="invalid_filename_path_traversal"):
        validate_file("../../etc/passwd", b"root:x:0:0")

