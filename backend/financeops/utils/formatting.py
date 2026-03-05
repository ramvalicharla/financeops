from __future__ import annotations

from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal


def format_decimal(value: Decimal, places: int = 2) -> str:
    """Format a Decimal to a fixed number of decimal places string."""
    quantizer = Decimal(10) ** -places
    return str(value.quantize(quantizer, rounding=ROUND_HALF_UP))


def round_financial(value: Decimal, places: int = 2) -> Decimal:
    """Round a Decimal using ROUND_HALF_UP (banker-safe for financial use)."""
    quantizer = Decimal(10) ** -places
    return value.quantize(quantizer, rounding=ROUND_HALF_UP)


def utc_now() -> datetime:
    """Return the current UTC datetime (timezone-aware)."""
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return utc_now().isoformat()


def format_currency(amount: Decimal, currency: str = "USD") -> str:
    """Format a Decimal amount with currency code."""
    return f"{currency} {format_decimal(amount, 2)}"


def truncate_for_log(value: str, max_len: int = 50) -> str:
    """Truncate a string for safe logging, appending ellipsis if cut."""
    if len(value) <= max_len:
        return value
    return value[:max_len] + "..."
