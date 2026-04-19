from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from financeops.db.models.gst import GstReturnLineItem

BLOCKED_ITC_CATEGORIES = {
    "motor_vehicle",
    "food_beverages",
    "personal_expenses",
    "membership_club",
    "health_insurance_employee",
}


@dataclass(slots=True)
class ItcEligibilityResult:
    itc_eligible: bool
    itc_blocked_reason: str | None
    reverse_itc: bool


def evaluate_itc_eligibility(
    *,
    line_item: GstReturnLineItem,
    appears_in_gstr2b: bool,
    today: date,
) -> ItcEligibilityResult:
    normalized_category = (line_item.expense_category or "").strip().lower()
    if normalized_category in BLOCKED_ITC_CATEGORIES:
        return ItcEligibilityResult(
            itc_eligible=False,
            itc_blocked_reason=f"blocked_category:{normalized_category}",
            reverse_itc=False,
        )

    if line_item.invoice_date is not None:
        if line_item.invoice_date < (today - timedelta(days=180)):
            if (line_item.payment_status or "").strip().upper() != "PAID":
                return ItcEligibilityResult(
                    itc_eligible=False,
                    itc_blocked_reason="rule_37_payment_overdue",
                    reverse_itc=True,
                )

    if not appears_in_gstr2b:
        return ItcEligibilityResult(
            itc_eligible=False,
            itc_blocked_reason="rule_36_missing_in_gstr2b",
            reverse_itc=False,
        )

    return ItcEligibilityResult(
        itc_eligible=True,
        itc_blocked_reason=None,
        reverse_itc=False,
    )
