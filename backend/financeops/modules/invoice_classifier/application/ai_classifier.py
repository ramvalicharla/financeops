from __future__ import annotations

import json
import re
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from financeops.llm.circuit_breaker import CircuitBreakerRegistry
from financeops.llm.gateway import gateway_generate
from financeops.modules.invoice_classifier.application.rule_engine import InvoiceInput


@dataclass(slots=True)
class AIResult:
    classification: str
    confidence: Decimal
    ai_reasoning: str
    method: str = "AI_GATEWAY"


_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


def _to_confidence(raw_confidence: object) -> Decimal:
    try:
        value = float(raw_confidence)
    except Exception:  # noqa: BLE001
        value = 0.0
    return Decimal(str(round(value, 4)))


async def classify_with_ai(
    invoice: InvoiceInput,
    tenant_id: UUID,
) -> AIResult:
    prompt = (
        "Vendor: " + invoice.vendor_name + "\n"
        "Description: " + invoice.line_description + "\n"
        "Amount: " + format(Decimal(str(invoice.invoice_amount)), "f") + "\n\n"
        "Classify this invoice into one of: "
        "FIXED_ASSET, PREPAID_EXPENSE, DIRECT_EXPENSE, CAPEX, OPEX, UNCERTAIN\n\n"
        "Respond with JSON only:\n"
        "{\n"
        '  "classification": "...",\n'
        '  "confidence": 0.95,\n'
        '  "reasoning": "..."\n'
        "}"
    )

    result = await gateway_generate(
        task_type="invoice_classifier",
        prompt=prompt,
        system_prompt="You are an accounting classifier. Return strict JSON only.",
        tenant_id=str(tenant_id),
        circuit_registry=CircuitBreakerRegistry(),
    )

    payload: dict[str, object] = {}
    raw = result.content.strip()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        match = _JSON_BLOCK.search(raw)
        if match:
            try:
                payload = json.loads(match.group(0))
            except json.JSONDecodeError:
                payload = {}

    classification = str(payload.get("classification", "UNCERTAIN")).upper()
    confidence = _to_confidence(payload.get("confidence", 0.0))
    reasoning = str(payload.get("reasoning", ""))
    return AIResult(
        classification=classification,
        confidence=confidence,
        ai_reasoning=reasoning,
    )


__all__ = ["AIResult", "classify_with_ai"]
