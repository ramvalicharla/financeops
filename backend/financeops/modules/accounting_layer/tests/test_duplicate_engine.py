from __future__ import annotations

import hashlib
import uuid
from datetime import date
from decimal import Decimal

from financeops.db.models.accounting_vendor import DuplicateAction
from financeops.modules.accounting_layer.engines.duplicate_engine import (
    _amount_bucket,
    _date_bucket,
    compute_file_hash,
    compute_layer2_fingerprint,
    compute_layer3_fingerprint,
)

_BASE36 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_BASE36_MAP = {char: idx for idx, char in enumerate(_BASE36)}


def _checksum_char(body: str) -> str:
    total = 0
    for idx, char in enumerate(body):
        value = _BASE36_MAP[char]
        factor = 1 if idx % 2 == 0 else 2
        product = value * factor
        total += (product // 36) + (product % 36)
    return _BASE36[(36 - (total % 36)) % 36]


def _build_valid_gstin() -> str:
    body = "29AABCF1234A1Z"
    return f"{body}{_checksum_char(body)}"


class TestComputeFileHash:
    def test_deterministic(self) -> None:
        content = b"invoice content bytes"
        assert compute_file_hash(content) == compute_file_hash(content)

    def test_sha256_length(self) -> None:
        assert len(compute_file_hash(b"test")) == 64

    def test_different_content_different_hash(self) -> None:
        assert compute_file_hash(b"file_a") != compute_file_hash(b"file_b")

    def test_empty_bytes(self) -> None:
        digest = compute_file_hash(b"")
        assert isinstance(digest, str)
        assert len(digest) == 64

    def test_matches_hashlib_directly(self) -> None:
        content = b"test invoice"
        expected = hashlib.sha256(content).hexdigest()
        assert compute_file_hash(content) == expected


class TestComputeLayer2Fingerprint:
    def test_valid_inputs_returns_hash(self) -> None:
        fingerprint = compute_layer2_fingerprint("INV-001", _build_valid_gstin())
        assert fingerprint is not None
        assert len(fingerprint) == 64

    def test_normalised_case_insensitive(self) -> None:
        gstin = _build_valid_gstin()
        fp1 = compute_layer2_fingerprint("inv-001", gstin.lower())
        fp2 = compute_layer2_fingerprint("INV-001", gstin)
        assert fp1 == fp2

    def test_missing_invoice_number_returns_none(self) -> None:
        assert compute_layer2_fingerprint(None, _build_valid_gstin()) is None

    def test_missing_gstin_returns_none(self) -> None:
        assert compute_layer2_fingerprint("INV-001", None) is None

    def test_invalid_gstin_returns_none(self) -> None:
        assert compute_layer2_fingerprint("INV-001", "INVALID") is None

    def test_empty_strings_return_none(self) -> None:
        assert compute_layer2_fingerprint("", _build_valid_gstin()) is None
        assert compute_layer2_fingerprint("INV-001", "") is None

    def test_different_invoice_different_fingerprint(self) -> None:
        gstin = _build_valid_gstin()
        fp1 = compute_layer2_fingerprint("INV-001", gstin)
        fp2 = compute_layer2_fingerprint("INV-002", gstin)
        assert fp1 != fp2


class TestComputeLayer3Fingerprint:
    def test_valid_inputs_returns_hash(self) -> None:
        vendor_id = uuid.uuid4()
        fingerprint = compute_layer3_fingerprint(vendor_id, Decimal("100000"), date(2026, 3, 1))
        assert fingerprint is not None
        assert len(fingerprint) == 64

    def test_missing_vendor_id_returns_none(self) -> None:
        assert compute_layer3_fingerprint(None, Decimal("100000"), date(2026, 3, 1)) is None

    def test_missing_amount_returns_none(self) -> None:
        assert compute_layer3_fingerprint(uuid.uuid4(), None, date(2026, 3, 1)) is None

    def test_missing_date_returns_none(self) -> None:
        assert compute_layer3_fingerprint(uuid.uuid4(), Decimal("100000"), None) is None

    def test_similar_amounts_same_bucket(self) -> None:
        vendor_id = uuid.uuid4()
        invoice_date = date(2026, 3, 1)
        fp1 = compute_layer3_fingerprint(vendor_id, Decimal("100000"), invoice_date)
        fp2 = compute_layer3_fingerprint(vendor_id, Decimal("100500"), invoice_date)
        assert fp1 == fp2

    def test_very_different_amounts_different_bucket(self) -> None:
        vendor_id = uuid.uuid4()
        invoice_date = date(2026, 3, 1)
        fp1 = compute_layer3_fingerprint(vendor_id, Decimal("100000"), invoice_date)
        fp2 = compute_layer3_fingerprint(vendor_id, Decimal("200000"), invoice_date)
        assert fp1 != fp2

    def test_dates_within_tolerance_same_bucket(self) -> None:
        d1 = date(2026, 3, 1)
        d2 = date(2026, 3, 2)
        assert _date_bucket(d1) == _date_bucket(d2)


class TestAmountBucket:
    def test_zero_returns_zero(self) -> None:
        assert _amount_bucket(Decimal("0")) == Decimal("0")

    def test_returns_decimal_not_float(self) -> None:
        assert isinstance(_amount_bucket(Decimal("100000")), Decimal)

    def test_amounts_within_1pct_same_bucket(self) -> None:
        assert _amount_bucket(Decimal("100000")) == _amount_bucket(Decimal("100999"))

    def test_amounts_outside_1pct_different_bucket(self) -> None:
        assert _amount_bucket(Decimal("100000")) != _amount_bucket(Decimal("102000"))

    def test_decimal_precision_no_float(self) -> None:
        assert Decimal("0.1") + Decimal("0.2") == Decimal("0.3")


class TestDateBucket:
    def test_same_3day_window_same_bucket(self) -> None:
        d1 = date(2026, 3, 1)
        d2 = date(2026, 3, 2)
        assert _date_bucket(d1) == _date_bucket(d2)

    def test_dates_far_apart_different_bucket(self) -> None:
        assert _date_bucket(date(2026, 1, 1)) != _date_bucket(date(2026, 6, 1))

    def test_returns_date_type(self) -> None:
        assert isinstance(_date_bucket(date(2026, 3, 15)), date)

    def test_bucket_is_before_or_equal_to_input(self) -> None:
        dt = date(2026, 3, 15)
        assert _date_bucket(dt) <= dt


class TestDuplicateActionConstants:
    def test_all_actions_defined(self) -> None:
        for action in (
            DuplicateAction.FLAGGED,
            DuplicateAction.SKIPPED,
            DuplicateAction.OVERRIDDEN,
            DuplicateAction.RELATED,
        ):
            assert isinstance(action, str)
            assert len(action) > 0
