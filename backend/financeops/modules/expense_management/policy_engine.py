from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from financeops.modules.expense_management.models import ExpensePolicy


@dataclass
class PolicyCheckResult:
    passed: bool
    violation_type: str | None
    violation_message: str | None
    requires_justification: bool
    is_hard_block: bool


class ExpensePolicyEngine:
    def __init__(self, policy: ExpensePolicy):
        self.policy = policy

    def _limit_for_category(self, category: str) -> Decimal | None:
        if category == "meals":
            return Decimal(str(self.policy.meal_limit_per_day))
        if category in {"travel", "accommodation"}:
            return Decimal(str(self.policy.travel_limit_per_night))
        return None

    def check(
        self,
        category: str,
        amount: Decimal,
        currency: str,
        claim_date: date,
        vendor_name: str,
        has_receipt: bool,
        existing_claims_same_day: list[Decimal] | None = None,
    ) -> PolicyCheckResult:
        """
        Run checks in this priority order (return first violation):

        1. Personal merchant (hard block)
           vendor_name.lower() contains any keyword in
           policy.personal_merchant_keywords

        2. Receipt missing (soft — requires justification)
           not has_receipt AND amount > receipt_required_above

        3. Hard limit (hard block)
           amount > category_limit * Decimal('1.5')

        4. Soft limit (soft — requires justification)
           amount > category_limit

        5. Round number (soft)
           policy.round_number_flag_enabled AND
           amount % Decimal('500') == Decimal('0') AND
           amount > Decimal('500')

        6. Weekend (soft)
           policy.weekend_flag_enabled AND
           claim_date.weekday() in (5, 6)

        If none triggered: return passed=True result.
        """
        del currency, existing_claims_same_day
        amount_decimal = Decimal(str(amount))
        vendor_lower = str(vendor_name or "").lower()

        for keyword in list(self.policy.personal_merchant_keywords or []):
            if str(keyword).lower() in vendor_lower:
                return PolicyCheckResult(
                    passed=False,
                    violation_type="personal_merchant",
                    violation_message="Vendor appears to be a personal merchant.",
                    requires_justification=False,
                    is_hard_block=True,
                )

        if (not has_receipt) and amount_decimal > Decimal(str(self.policy.receipt_required_above)):
            return PolicyCheckResult(
                passed=False,
                violation_type="receipt_missing",
                violation_message="Receipt is required for this amount.",
                requires_justification=True,
                is_hard_block=False,
            )

        category_limit = self._limit_for_category(category)
        if category_limit is not None:
            hard_limit = category_limit * Decimal("1.5")
            if amount_decimal > hard_limit:
                return PolicyCheckResult(
                    passed=False,
                    violation_type="hard_limit",
                    violation_message="Claim exceeds hard policy limit.",
                    requires_justification=False,
                    is_hard_block=True,
                )
            if amount_decimal > category_limit:
                return PolicyCheckResult(
                    passed=False,
                    violation_type="soft_limit",
                    violation_message="Claim exceeds policy limit and needs justification.",
                    requires_justification=True,
                    is_hard_block=False,
                )

        if (
            bool(self.policy.round_number_flag_enabled)
            and amount_decimal > Decimal("500")
            and amount_decimal % Decimal("500") == Decimal("0")
        ):
            return PolicyCheckResult(
                passed=False,
                violation_type="round_number",
                violation_message="Round-number expense flagged for review.",
                requires_justification=True,
                is_hard_block=False,
            )

        if bool(self.policy.weekend_flag_enabled) and claim_date.weekday() in (5, 6):
            return PolicyCheckResult(
                passed=False,
                violation_type="weekend",
                violation_message="Weekend expense flagged for review.",
                requires_justification=True,
                is_hard_block=False,
            )

        return PolicyCheckResult(
            passed=True,
            violation_type=None,
            violation_message=None,
            requires_justification=False,
            is_hard_block=False,
        )

