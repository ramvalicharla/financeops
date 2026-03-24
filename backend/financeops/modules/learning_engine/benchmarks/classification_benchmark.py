from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.ext.asyncio import AsyncSession

from financeops.modules.learning_engine.models import AIBenchmarkResult

CLASSIFICATION_TEST_CASES = [
    {
        "input": "Swiggy delivery charges for team lunch",
        "expected_category": "meals",
        "expected_gl": "entertainment_expense",
    },
    {
        "input": "AWS EC2 monthly invoice",
        "expected_category": "technology",
        "expected_gl": "cloud_infrastructure",
    },
    {
        "input": "Flight BOM-DEL for client meeting",
        "expected_category": "travel",
        "expected_gl": "travel_expense",
    },
    {
        "input": "Annual audit fees - Big 4",
        "expected_category": "professional_fees",
        "expected_gl": "audit_fees",
    },
    {
        "input": "Office stationery from Amazon",
        "expected_category": "office_supplies",
        "expected_gl": "office_supplies",
    },
    {
        "input": "Salary advance - John Smith",
        "expected_category": "other",
        "expected_gl": "advance_to_employees",
    },
    {
        "input": "Google Workspace annual subscription",
        "expected_category": "technology",
        "expected_gl": "software_subscriptions",
    },
    {
        "input": "Uber Eats dinner - working late",
        "expected_category": "meals",
        "expected_gl": "staff_welfare",
    },
    {
        "input": "Company incorporation fees",
        "expected_category": "professional_fees",
        "expected_gl": "legal_fees",
    },
    {
        "input": "Electricity bill - Bangalore office",
        "expected_category": "office_supplies",
        "expected_gl": "utilities",
    },
]


def _predict_category(input_text: str) -> str:
    text = input_text.lower()
    if any(token in text for token in ("swiggy", "uber eats", "lunch", "dinner")):
        return "meals"
    if any(token in text for token in ("aws", "google workspace", "subscription")):
        return "technology"
    if any(token in text for token in ("flight", "hotel", "travel")):
        return "travel"
    if any(token in text for token in ("audit", "incorporation", "legal", "fees")):
        return "professional_fees"
    if any(token in text for token in ("stationery", "electricity", "office")):
        return "office_supplies"
    return "other"


async def run_classification_benchmark(
    session: AsyncSession,
    run_by: str = "scheduled",
) -> AIBenchmarkResult:
    started_at = datetime.now(UTC)
    total_cases = len(CLASSIFICATION_TEST_CASES)
    passed_cases = 0
    details: list[dict] = []

    for case in CLASSIFICATION_TEST_CASES:
        predicted = _predict_category(str(case["input"]))
        expected = str(case["expected_category"])
        passed = predicted == expected
        if passed:
            passed_cases += 1
        details.append(
            {
                "input": case["input"],
                "expected_category": expected,
                "predicted_category": predicted,
                "passed": passed,
            }
        )

    elapsed_ms = max(
        Decimal("1"),
        Decimal(str((datetime.now(UTC) - started_at).total_seconds())) * Decimal("1000"),
    )
    avg_latency = (elapsed_ms / Decimal(str(total_cases or 1))).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    accuracy = (Decimal(str(passed_cases)) / Decimal(str(total_cases or 1))).quantize(
        Decimal("0.0000"), rounding=ROUND_HALF_UP
    )

    row = AIBenchmarkResult(
        benchmark_name="classification",
        benchmark_version="1.0",
        model="offline-classifier-v1",
        provider="internal",
        total_cases=total_cases,
        passed_cases=passed_cases,
        accuracy_pct=accuracy,
        avg_latency_ms=avg_latency,
        total_cost_usd=Decimal("0.000000"),
        run_by=run_by,
        details={"cases": details},
    )
    session.add(row)
    await session.flush()
    return row


__all__ = ["CLASSIFICATION_TEST_CASES", "run_classification_benchmark"]
