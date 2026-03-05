from __future__ import annotations

import pytest

from financeops.utils.determinism import (
    canonical_json_dumps,
    canonical_json_bytes,
    sha256_hex_bytes,
    sha256_hex_text,
    stable_finding_id,
    payload_contains_nondeterministic_markers,
)


def test_canonical_json_sorts_keys():
    data = {"z": 1, "a": 2, "m": 3}
    result = canonical_json_dumps(data)
    # Keys must be sorted
    assert result == '{"a":2,"m":3,"z":1}'


def test_canonical_json_is_deterministic():
    data = {"b": [3, 1, 2], "a": {"y": "yes", "x": "no"}}
    result1 = canonical_json_dumps(data)
    result2 = canonical_json_dumps(data)
    assert result1 == result2


def test_canonical_json_bytes_is_utf8():
    data = {"key": "value"}
    result = canonical_json_bytes(data)
    assert isinstance(result, bytes)
    assert result == canonical_json_dumps(data).encode("utf-8")


def test_sha256_hex_text_returns_64_chars():
    result = sha256_hex_text("hello world")
    assert len(result) == 64
    assert all(c in "0123456789abcdef" for c in result)


def test_sha256_hex_deterministic():
    assert sha256_hex_text("test") == sha256_hex_text("test")
    assert sha256_hex_text("test") != sha256_hex_text("TEST")


def test_stable_finding_id_is_deterministic():
    fid1 = stable_finding_id(
        input_hash="abc123",
        rule_id="RULE_001",
        location="line:42",
        normalized_evidence={"amount": 1000},
    )
    fid2 = stable_finding_id(
        input_hash="abc123",
        rule_id="RULE_001",
        location="line:42",
        normalized_evidence={"amount": 1000},
    )
    assert fid1 == fid2
    assert len(fid1) == 64


def test_stable_finding_id_different_for_different_inputs():
    fid1 = stable_finding_id(
        input_hash="abc123", rule_id="RULE_001", location="line:42",
        normalized_evidence={"amount": 1000},
    )
    fid2 = stable_finding_id(
        input_hash="abc123", rule_id="RULE_002", location="line:42",
        normalized_evidence={"amount": 1000},
    )
    assert fid1 != fid2


def test_payload_nondeterministic_markers_detected():
    payload_with_timestamp = {"action": "login", "timestamp": "2026-01-01T00:00:00Z"}
    assert payload_contains_nondeterministic_markers(payload_with_timestamp) is True


def test_payload_without_nondeterministic_markers():
    payload = {"action": "login", "user": "alice", "role": "admin"}
    assert payload_contains_nondeterministic_markers(payload) is False
