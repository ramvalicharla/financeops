from __future__ import annotations

from decimal import Decimal

import pytest

from financeops.services.fx.normalization import (
    CANONICAL_RATE_CONVENTION,
    normalize_currency_code,
    normalize_rate_decimal,
)


def test_canonical_rate_convention_declared() -> None:
    assert CANONICAL_RATE_CONVENTION == "1 base_currency = X quote_currency"


def test_normalize_currency_code_maps_ntd_to_twd() -> None:
    assert normalize_currency_code("ntd") == "TWD"


def test_normalize_currency_code_rejects_invalid_iso() -> None:
    with pytest.raises(ValueError):
        normalize_currency_code("ZZZ")


def test_normalize_rate_decimal_quantizes_to_6dp() -> None:
    assert normalize_rate_decimal(Decimal("83.1234567")) == Decimal("83.123457")


def test_normalize_rate_decimal_rejects_non_positive() -> None:
    with pytest.raises(ValueError):
        normalize_rate_decimal(Decimal("0"))
