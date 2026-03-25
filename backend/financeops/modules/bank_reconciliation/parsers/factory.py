from __future__ import annotations

from .axis import AxisBankParser
from .base import BaseBankParser
from .hdfc import HDFCBankParser
from .icici import ICICIBankParser
from .sbi import SBIBankParser

BANK_PARSERS: dict[str, type[BaseBankParser]] = {
    "hdfc": HDFCBankParser,
    "icici": ICICIBankParser,
    "sbi": SBIBankParser,
    "axis": AxisBankParser,
}


def get_parser(bank_name: str) -> BaseBankParser:
    key = bank_name.lower().replace(" ", "_").replace("bank", "").strip("_")
    parser_class = BANK_PARSERS.get(key)
    if not parser_class:
        raise ValueError(
            f"No parser for bank: {bank_name}. "
            f"Supported: {list(BANK_PARSERS.keys())}"
        )
    return parser_class()


def detect_bank_from_content(content: str) -> str:
    """
    Auto-detect bank from statement content.
    Checks header row for bank-specific patterns.
    """
    first_lines = content[:500].upper()
    if "HDFC" in first_lines:
        return "hdfc"
    if "ICICI" in first_lines:
        return "icici"
    if "STATE BANK" in first_lines or "SBI" in first_lines:
        return "sbi"
    if "AXIS" in first_lines:
        return "axis"
    if "KOTAK" in first_lines:
        return "kotak"
    raise ValueError("Could not auto-detect bank. Please specify bank name.")
