from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from financeops.modules.financial_risk_engine.domain.enums import SeverityLevel

SIX_DP = Decimal("0.000001")
ONE = Decimal("1")
ZERO = Decimal("0")

SEVERITY_RANK = {
    SeverityLevel.INFO.value: 0,
    SeverityLevel.LOW.value: 1,
    SeverityLevel.MEDIUM.value: 2,
    SeverityLevel.HIGH.value: 3,
    SeverityLevel.CRITICAL.value: 4,
}


def q6(value: Decimal | int | float | str) -> Decimal:
    return Decimal(str(value)).quantize(SIX_DP, rounding=ROUND_HALF_UP)


def clamp01(value: Decimal) -> Decimal:
    if value < ZERO:
        return ZERO
    if value > ONE:
        return ONE
    return q6(value)


def severity_rank(value: str) -> int:
    return SEVERITY_RANK.get(value, 0)
