from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP


PF_EMPLOYER_RATE = Decimal("0.12")
PF_EMPLOYEE_RATE = Decimal("0.12")
PF_MONTHLY_CAP = Decimal("1800.00")
ESI_EMPLOYER_RATE = Decimal("0.0325")
ESI_EMPLOYEE_RATE = Decimal("0.0075")
ESI_APPLICABILITY_LIMIT = Decimal("21000.00")

# TDS slabs — verify with finance team before going live
# TODO: confirm FY2025-26 slabs with finance team
TDS_SLABS_FY2526: list[tuple[Decimal, Decimal, Decimal]] = [
    (Decimal("0"), Decimal("300000"), Decimal("0")),
    (Decimal("300001"), Decimal("700000"), Decimal("0.05")),
    (Decimal("700001"), Decimal("1000000"), Decimal("0.10")),
    (Decimal("1000001"), Decimal("1200000"), Decimal("0.15")),
    (Decimal("1200001"), Decimal("1500000"), Decimal("0.20")),
    (Decimal("1500001"), Decimal("9999999"), Decimal("0.30")),
]
TDS_SLABS_CONFIRMED = False


def _q2(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def compute_pf(basic_salary: Decimal) -> dict[str, Decimal]:
    employee = min(_q2(basic_salary * PF_EMPLOYEE_RATE), PF_MONTHLY_CAP)
    employer = min(_q2(basic_salary * PF_EMPLOYER_RATE), PF_MONTHLY_CAP)
    return {"employee": employee, "employer": employer}


def compute_esi(gross_salary: Decimal) -> dict[str, Decimal]:
    if gross_salary > ESI_APPLICABILITY_LIMIT:
        return {"employee": Decimal("0.00"), "employer": Decimal("0.00")}
    return {
        "employee": _q2(gross_salary * ESI_EMPLOYEE_RATE),
        "employer": _q2(gross_salary * ESI_EMPLOYER_RATE),
    }


def compute_tds(annual_income: Decimal) -> Decimal:
    if not TDS_SLABS_CONFIRMED:
        raise NotImplementedError(
            "TDS slabs not confirmed by finance team. "
            "Set TDS_SLABS_CONFIRMED = True after verifying FY2025-26 slabs."
        )

    tax = Decimal("0.00")
    for lower_bound, upper_bound, rate in TDS_SLABS_FY2526:
        if annual_income < lower_bound:
            continue
        taxable_band = min(annual_income, upper_bound) - lower_bound + Decimal("1")
        if taxable_band <= Decimal("0"):
            continue
        tax += taxable_band * rate
        if annual_income <= upper_bound:
            break
    return _q2(tax)
