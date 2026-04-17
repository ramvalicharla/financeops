from __future__ import annotations

from financeops.utils.gstin import INDIA_STATE_CODES, extract_state_code, validate_gstin, validate_pan

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


def _build_gstin(state_code: str, pan: str = "AABCF1234A", entity_code: str = "1") -> str:
    body = f"{state_code}{pan}{entity_code}Z"
    return f"{body}{_checksum_char(body)}"


def test_gstin_checksum_valid() -> None:
    gstin = _build_gstin("36")
    assert validate_gstin(gstin) is True


def test_gstin_checksum_invalid() -> None:
    gstin = _build_gstin("36")
    invalid_last = "0" if gstin[-1] != "0" else "1"
    invalid = f"{gstin[:-1]}{invalid_last}"
    assert validate_gstin(invalid) is False


def test_all_state_codes_are_two_digits() -> None:
    assert all(len(code) == 2 and code.isdigit() for code in INDIA_STATE_CODES)


def test_extract_state_code_all_known_states() -> None:
    for code in INDIA_STATE_CODES:
        gstin = _build_gstin(code)
        extracted = extract_state_code(gstin)
        assert extracted == code


def test_gstin_pan_embedded_correctly() -> None:
    gstin = _build_gstin("27", pan="AABCF1234A")
    assert validate_pan(gstin[2:12]) is True


def test_gstin_state_code_00_rejected() -> None:
    assert validate_gstin("00AAAAA0000A1Z5") is False


def test_gstin_state_code_29_karnataka_valid() -> None:
    assert validate_gstin(_build_gstin("29")) is True


def test_gstin_state_code_38_ladakh_valid() -> None:
    assert validate_gstin(_build_gstin("38")) is True


def test_gstin_state_code_39_invalid() -> None:
    assert validate_gstin(_build_gstin("39")) is False
