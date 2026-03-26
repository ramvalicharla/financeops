from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from financeops.modules.invoice_classifier.models import ClassificationRule

CONFIDENCE_THRESHOLD = Decimal("0.8500")


@dataclass(slots=True)
class InvoiceInput:
    invoice_number: str
    vendor_name: str
    line_description: str
    invoice_amount: Decimal
    invoice_date: str | None = None


@dataclass(slots=True)
class RuleResult:
    classification: str
    confidence: Decimal
    rule_matched: str
    method: str = "RULE_ENGINE"


def _contains(source: str, pattern: str) -> bool:
    return pattern.lower() in source.lower()


def apply_rules(
    invoice: InvoiceInput,
    rules: list[ClassificationRule],
) -> RuleResult | None:
    active_rules = [row for row in rules if row.is_active]
    active_rules.sort(key=lambda row: row.priority)

    vendor = invoice.vendor_name or ""
    description = invoice.line_description or ""
    amount = Decimal(str(invoice.invoice_amount))

    for rule in active_rules:
        matched = False
        rule_type = rule.pattern_type
        pattern_value = rule.pattern_value

        if rule_type == "VENDOR_NAME":
            matched = _contains(vendor, pattern_value)
        elif rule_type == "DESCRIPTION_KEYWORD":
            matched = _contains(description, pattern_value)
        elif rule_type == "AMOUNT_RANGE":
            min_ok = True if rule.amount_min is None else amount >= Decimal(str(rule.amount_min))
            max_ok = True if rule.amount_max is None else amount <= Decimal(str(rule.amount_max))
            matched = min_ok and max_ok
        elif rule_type == "VENDOR_AND_KEYWORD":
            vendor_part, _, keyword_part = pattern_value.partition("|")
            matched = _contains(vendor, vendor_part.strip()) and _contains(description, keyword_part.strip() or vendor_part.strip())

        if matched:
            return RuleResult(
                classification=rule.classification,
                confidence=Decimal(str(rule.confidence)),
                rule_matched=rule.rule_name,
            )

    return None


__all__ = ["CONFIDENCE_THRESHOLD", "InvoiceInput", "RuleResult", "apply_rules"]
