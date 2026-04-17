from __future__ import annotations

import re

INDIA_STATE_CODES: dict[str, str] = {
    "01": "Jammu & Kashmir",
    "02": "Himachal Pradesh",
    "03": "Punjab",
    "04": "Chandigarh",
    "05": "Uttarakhand",
    "06": "Haryana",
    "07": "Delhi",
    "08": "Rajasthan",
    "09": "Uttar Pradesh",
    "10": "Bihar",
    "11": "Sikkim",
    "12": "Arunachal Pradesh",
    "13": "Nagaland",
    "14": "Manipur",
    "15": "Mizoram",
    "16": "Tripura",
    "17": "Meghalaya",
    "18": "Assam",
    "19": "West Bengal",
    "20": "Jharkhand",
    "21": "Odisha",
    "22": "Chhattisgarh",
    "23": "Madhya Pradesh",
    "24": "Gujarat",
    "25": "Daman & Diu",
    "26": "Dadra & Nagar Haveli",
    "27": "Maharashtra",
    "28": "Andhra Pradesh (old)",
    "29": "Karnataka",
    "30": "Goa",
    "31": "Lakshadweep",
    "32": "Kerala",
    "33": "Tamil Nadu",
    "34": "Puducherry",
    "35": "Andaman & Nicobar",
    "36": "Telangana",
    "37": "Andhra Pradesh",
    "38": "Ladakh",
    "97": "Other Territory",
    "99": "Centre Jurisdiction",
}

_PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
_TAN_RE = re.compile(r"^[A-Z]{4}[0-9]{5}[A-Z]$")
_GSTIN_RE = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][A-Z0-9]Z[A-Z0-9]$")
VALID_STATE_CODES = {f"{i:02d}" for i in range(1, 39)}
_BASE36 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_VALUE_BY_CHAR = {char: idx for idx, char in enumerate(_BASE36)}


def extract_state_code(gstin: str) -> str | None:
    value = str(gstin or "").strip().upper()
    if len(value) != 15:
        return None
    state_code = value[:2]
    if state_code not in INDIA_STATE_CODES:
        return None
    return state_code


def _checksum_char(body: str) -> str | None:
    if len(body) != 14:
        return None
    total = 0
    for idx, char in enumerate(body):
        code_point = _VALUE_BY_CHAR.get(char)
        if code_point is None:
            return None
        factor = 1 if idx % 2 == 0 else 2
        product = code_point * factor
        total += (product // 36) + (product % 36)
    check_value = (36 - (total % 36)) % 36
    return _BASE36[check_value]


def validate_gstin(gstin: str) -> bool:
    value = str(gstin or "").strip().upper()
    if len(value) != 15:
        return False
    if _GSTIN_RE.fullmatch(value) is None:
        return False

    state_code = value[:2]
    if state_code not in VALID_STATE_CODES:
        return False

    pan_part = value[2:12]
    if not validate_pan(pan_part):
        return False

    expected = _checksum_char(value[:14])
    return expected is not None and value[-1] == expected


def validate_pan(pan: str) -> bool:
    value = str(pan or "").strip().upper()
    return _PAN_RE.fullmatch(value) is not None


def validate_tan(tan: str) -> bool:
    value = str(tan or "").strip().upper()
    return _TAN_RE.fullmatch(value) is not None


__all__ = [
    "INDIA_STATE_CODES",
    "VALID_STATE_CODES",
    "extract_state_code",
    "validate_gstin",
    "validate_pan",
    "validate_tan",
]
