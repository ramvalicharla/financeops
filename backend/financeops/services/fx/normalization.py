from __future__ import annotations

import re
from decimal import Decimal, ROUND_HALF_UP

CANONICAL_RATE_CONVENTION = "1 base_currency = X quote_currency"
RATE_PRECISION = Decimal("0.000001")
_CURRENCY_PATTERN = re.compile(r"^[A-Z]{3}$")
_ALIAS_MAP: dict[str, str] = {"NTD": "TWD"}

# Explicitly supported currencies from Phase 1B requirements.
REQUIRED_SUPPORTED_CURRENCIES: frozenset[str] = frozenset(
    {"INR", "GBP", "EUR", "USD", "AUD", "CAD", "TWD", "CHF"}
)

# Conservative fallback set if Babel is unavailable at runtime.
_FALLBACK_ISO_CODES: frozenset[str] = frozenset(
    {
        "AED",
        "AUD",
        "BRL",
        "CAD",
        "CHF",
        "CNY",
        "EUR",
        "GBP",
        "HKD",
        "INR",
        "JPY",
        "KRW",
        "MXN",
        "NOK",
        "NZD",
        "SEK",
        "SGD",
        "TWD",
        "USD",
        "ZAR",
    }
)

try:
    from babel.numbers import list_currencies
except Exception:  # pragma: no cover - dependency fallback
    list_currencies = None  # type: ignore[assignment]

if list_currencies is not None:
    try:
        _BABEL_CURRENCY_CODES = frozenset(
            str(code).upper() for code in list_currencies(locale="en_US")
        )
    except Exception:  # pragma: no cover - dependency fallback
        _BABEL_CURRENCY_CODES = None
else:  # pragma: no cover - dependency fallback
    _BABEL_CURRENCY_CODES = None


def normalize_currency_code(currency_code: str) -> str:
    code = currency_code.strip().upper()
    code = _ALIAS_MAP.get(code, code)
    if not _CURRENCY_PATTERN.fullmatch(code):
        raise ValueError(f"Invalid currency code format: {currency_code}")
    if not is_valid_iso_4217_currency(code):
        raise ValueError(f"Invalid ISO 4217 currency code: {currency_code}")
    return code


def is_valid_iso_4217_currency(currency_code: str) -> bool:
    code = currency_code.strip().upper()
    if not _CURRENCY_PATTERN.fullmatch(code):
        return False
    if _BABEL_CURRENCY_CODES is None:
        return code in _FALLBACK_ISO_CODES
    return code in _BABEL_CURRENCY_CODES


def normalize_rate_decimal(rate: Decimal) -> Decimal:
    if rate <= Decimal("0"):
        raise ValueError("FX rate must be greater than zero")
    return rate.quantize(RATE_PRECISION, rounding=ROUND_HALF_UP)


def normalize_currency_pair(base_currency: str, quote_currency: str) -> tuple[str, str]:
    base = normalize_currency_code(base_currency)
    quote = normalize_currency_code(quote_currency)
    return base, quote
