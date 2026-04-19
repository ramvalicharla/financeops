from __future__ import annotations

from decimal import Decimal

import pytest

from financeops.modules.payroll_gl_norm.application.statutory_deduction_service import (
    compute_esi,
    compute_pf,
    compute_tds,
)


def test_pf_employer_capped_at_1800_not_higher() -> None:
    result = compute_pf(Decimal("50000.00"))
    assert result["employer"] == Decimal("1800.00")


def test_pf_employee_capped_at_1800() -> None:
    result = compute_pf(Decimal("50000.00"))
    assert result["employee"] == Decimal("1800.00")


def test_esi_applicable_at_21000() -> None:
    result = compute_esi(Decimal("21000.00"))
    assert result["employee"] == Decimal("157.50")
    assert result["employer"] == Decimal("682.50")


def test_esi_not_applicable_at_21001() -> None:
    result = compute_esi(Decimal("21001.00"))
    assert result["employee"] == Decimal("0.00")
    assert result["employer"] == Decimal("0.00")


def test_tds_raises_not_implemented_until_confirmed() -> None:
    with pytest.raises(NotImplementedError):
        compute_tds(Decimal("900000.00"))
