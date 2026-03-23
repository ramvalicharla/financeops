from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.ext.asyncio import AsyncSession

from financeops.modules.fdd.models import FDDEngagement


def _q2(value: Decimal) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


async def _load_debt_inputs(session: AsyncSession, engagement: FDDEngagement) -> dict:
    del session, engagement
    return {
        "financial_debt": Decimal("500.00"),
        "cash_and_equivalents": Decimal("200.00"),
        "debt_like_items": [
            {
                "description": "Deferred revenue obligations",
                "amount": Decimal("70.00"),
                "category": "deferred_revenue",
            },
            {
                "description": "Lease liabilities",
                "amount": Decimal("30.00"),
                "category": "lease_liability",
            },
        ],
        "notes": [
            "Deferred revenue treated as debt-like item.",
            "Lease liabilities included in net debt bridge.",
        ],
    }


async def compute_debt_review(
    session: AsyncSession,
    engagement: FDDEngagement,
) -> dict:
    payload = await _load_debt_inputs(session, engagement)
    financial_debt = _q2(Decimal(str(payload["financial_debt"])))
    cash = _q2(Decimal(str(payload["cash_and_equivalents"])))
    debt_like_items = payload.get("debt_like_items", [])
    total_debt_like = _q2(
        sum((Decimal(str(item.get("amount", "0"))) for item in debt_like_items), start=Decimal("0"))
    )
    net_debt = _q2(financial_debt + total_debt_like - cash)

    findings = [
        {
            "finding_type": "adjustment",
            "severity": "high" if net_debt > Decimal("300") else "medium",
            "title": "Net debt bridge identified",
            "description": "Debt and debt-like items reduce equity value at close.",
            "financial_impact": net_debt,
            "recommended_action": "Include debt-like schedule in completion accounts.",
        }
    ]

    return {
        "financial_debt": financial_debt,
        "debt_like_items": [
            {
                "description": str(item.get("description", "")),
                "amount": _q2(Decimal(str(item.get("amount", "0")))),
                "category": str(item.get("category", "other")),
            }
            for item in debt_like_items
        ],
        "total_debt_like": total_debt_like,
        "cash_and_equivalents": cash,
        "net_debt": net_debt,
        "recommended_price_adjustment": net_debt,
        "notes": [str(note) for note in payload.get("notes", [])],
        "findings": findings,
    }


__all__ = ["compute_debt_review", "_load_debt_inputs"]
