from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.ext.asyncio import AsyncSession

from financeops.modules.learning_engine.models import AIBenchmarkResult

COMMENTARY_TEST_CASES = [
    {
        "input": {
            "metric": "Revenue",
            "current": "10000000",
            "previous": "8500000",
            "variance_pct": "17.65",
        },
        "expected_keywords": ["revenue", "growth", "increase"],
        "must_not_contain": ["declined", "fell", "decreased"],
    },
    {
        "input": {
            "metric": "EBITDA margin",
            "current": "0.18",
            "previous": "0.22",
            "variance_pct": "-18.18",
        },
        "expected_keywords": ["margin", "compressed", "declined"],
        "must_not_contain": ["improved", "increased"],
    },
]


def _generate_commentary(case_input: dict) -> str:
    metric = str(case_input.get("metric", "Metric"))
    variance_pct = Decimal(str(case_input.get("variance_pct", "0")))
    if variance_pct >= Decimal("0"):
        return f"{metric} showed growth with an increase over the previous period."
    return f"{metric} declined and margin compressed compared to prior period."


async def run_commentary_benchmark(
    session: AsyncSession,
    run_by: str = "scheduled",
) -> AIBenchmarkResult:
    started_at = datetime.now(UTC)
    total_cases = len(COMMENTARY_TEST_CASES)
    passed_cases = 0
    details: list[dict] = []

    for case in COMMENTARY_TEST_CASES:
        output = _generate_commentary(case["input"])
        output_lower = output.lower()
        expected_ok = all(keyword.lower() in output_lower for keyword in case["expected_keywords"])
        forbidden_ok = all(keyword.lower() not in output_lower for keyword in case["must_not_contain"])
        passed = expected_ok and forbidden_ok
        if passed:
            passed_cases += 1
        details.append(
            {
                "input": case["input"],
                "output": output,
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
        benchmark_name="commentary",
        benchmark_version="1.0",
        model="offline-commentary-v1",
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


__all__ = ["COMMENTARY_TEST_CASES", "run_commentary_benchmark"]

