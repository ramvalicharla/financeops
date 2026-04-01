from __future__ import annotations

import re
from decimal import Decimal

from financeops.core.exceptions import ValidationError

_NUMBER_PATTERN = re.compile(r"-?\d+(?:\.\d+)?")


def _to_decimal_set(values: list[Decimal | int | float | str]) -> set[Decimal]:
    payload: set[Decimal] = set()
    for value in values:
        payload.add(Decimal(str(value)).quantize(Decimal("0.000001")))
    return payload


def validate_generated_text_against_facts(
    *,
    text: str,
    allowed_numbers: list[Decimal | int | float | str],
    tolerance: Decimal = Decimal("0.01"),
) -> None:
    """
    Guardrail for AI narrative/explanation:
    numbers present in generated text must be grounded in deterministic facts.
    """
    if not text.strip():
        raise ValidationError("Generated text cannot be empty.")

    allowed = _to_decimal_set(allowed_numbers)
    discovered_tokens = _NUMBER_PATTERN.findall(text)
    discovered: list[Decimal] = []
    for token in discovered_tokens:
        # Ignore likely identifiers (account codes / years / references).
        if "." not in token and len(token.strip("-")) >= 4:
            continue
        discovered.append(Decimal(token).quantize(Decimal("0.000001")))

    for value in discovered:
        if not any(abs(value - candidate) <= tolerance for candidate in allowed):
            raise ValidationError(
                f"Validation layer rejected output: number {value} not in deterministic facts."
            )
