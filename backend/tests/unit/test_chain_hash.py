from __future__ import annotations

import pytest

from financeops.utils.chain_hash import (
    GENESIS_HASH,
    ChainVerificationResult,
    compute_chain_hash,
    verify_chain,
)


def _make_record(data: dict, previous_hash: str) -> dict:
    """Helper: build a record dict with chain_hash computed."""
    chain_hash = compute_chain_hash(data, previous_hash)
    return {**data, "chain_hash": chain_hash, "previous_hash": previous_hash}


def test_genesis_hash_is_64_zeros():
    assert GENESIS_HASH == "0" * 64
    assert len(GENESIS_HASH) == 64


def test_compute_chain_hash_returns_64_char_hex():
    result = compute_chain_hash({"foo": "bar"}, GENESIS_HASH)
    assert len(result) == 64
    assert all(c in "0123456789abcdef" for c in result)


def test_compute_chain_hash_is_deterministic():
    data = {"tenant_id": "abc", "action": "login", "amount": "100.00"}
    hash1 = compute_chain_hash(data, GENESIS_HASH)
    hash2 = compute_chain_hash(data, GENESIS_HASH)
    assert hash1 == hash2


def test_different_data_produces_different_hash():
    hash_a = compute_chain_hash({"action": "login"}, GENESIS_HASH)
    hash_b = compute_chain_hash({"action": "logout"}, GENESIS_HASH)
    assert hash_a != hash_b


def test_different_previous_hash_produces_different_hash():
    data = {"action": "login"}
    hash_a = compute_chain_hash(data, GENESIS_HASH)
    hash_b = compute_chain_hash(data, "a" * 64)
    assert hash_a != hash_b


def test_chained_hashes_depend_on_previous():
    record1_data = {"action": "register"}
    record1 = _make_record(record1_data, GENESIS_HASH)

    record2_data = {"action": "login"}
    record2 = _make_record(record2_data, record1["chain_hash"])

    # record2's previous_hash must equal record1's chain_hash
    assert record2["previous_hash"] == record1["chain_hash"]
    # Changing record1 should cascade and break record2
    assert record2["chain_hash"] != record1["chain_hash"]


def test_verify_chain_passes_on_valid_chain():
    r1_data = {"action": "register"}
    r1 = _make_record(r1_data, GENESIS_HASH)

    r2_data = {"action": "login"}
    r2 = _make_record(r2_data, r1["chain_hash"])

    r3_data = {"action": "update_role"}
    r3 = _make_record(r3_data, r2["chain_hash"])

    result: ChainVerificationResult = verify_chain([r1, r2, r3])
    assert result.is_valid is True
    assert result.total_records == 3
    assert result.first_broken_at is None


def test_verify_chain_detects_tampered_middle_record():
    r1_data = {"action": "register"}
    r1 = _make_record(r1_data, GENESIS_HASH)

    r2_data = {"action": "login"}
    r2 = _make_record(r2_data, r1["chain_hash"])

    r3_data = {"action": "update_role"}
    r3 = _make_record(r3_data, r2["chain_hash"])

    # Tamper with record 2's data (but leave chain_hash as-is)
    tampered_r2 = {**r2, "action": "TAMPERED"}
    result = verify_chain([r1, tampered_r2, r3])
    assert result.is_valid is False
    assert result.first_broken_at == 1  # 0-based index of tampered record


def test_verify_chain_detects_wrong_first_previous_hash():
    r1_data = {"action": "register"}
    wrong_previous = "b" * 64
    r1 = _make_record(r1_data, wrong_previous)
    # first record must have GENESIS_HASH as previous_hash
    result = verify_chain([r1])
    assert result.is_valid is False
    assert result.first_broken_at == 0


def test_verify_chain_empty_list():
    result = verify_chain([])
    assert result.is_valid is True
    assert result.total_records == 0


def test_verify_chain_single_valid_record():
    r1_data = {"action": "register"}
    r1 = _make_record(r1_data, GENESIS_HASH)
    result = verify_chain([r1])
    assert result.is_valid is True
