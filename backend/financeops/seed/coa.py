from __future__ import annotations

import asyncio

from sqlalchemy.dialects.postgresql import insert

from financeops.db.session import AsyncSessionLocal
from financeops.modules.coa.models import CoaIndustryTemplate


_INDUSTRY_TEMPLATES: list[dict[str, object]] = [
    {
        "code": "SOFTWARE_SAAS",
        "name": "Software & SaaS",
        "description": "Chart of accounts template for software and SaaS businesses.",
        "is_active": True,
    },
    {
        "code": "IT_SERVICES",
        "name": "IT Services",
        "description": "Chart of accounts template for IT and consulting service businesses.",
        "is_active": True,
    },
    {
        "code": "RETAIL",
        "name": "Retail",
        "description": "Chart of accounts template for retail operations.",
        "is_active": True,
    },
    {
        "code": "MANUFACTURING",
        "name": "Manufacturing",
        "description": "Chart of accounts template for manufacturing businesses.",
        "is_active": True,
    },
    {
        "code": "TRADING",
        "name": "Trading",
        "description": "Chart of accounts template for trading businesses.",
        "is_active": True,
    },
    {
        "code": "REAL_ESTATE",
        "name": "Real Estate",
        "description": "Chart of accounts template for real estate businesses.",
        "is_active": True,
    },
    {
        "code": "FINANCIAL_SERVICES",
        "name": "Financial Services",
        "description": "Chart of accounts template for financial services businesses.",
        "is_active": True,
    },
    {
        "code": "HOSPITALITY",
        "name": "Hospitality",
        "description": "Chart of accounts template for hospitality businesses.",
        "is_active": True,
    },
    {
        "code": "HEALTHCARE",
        "name": "Healthcare",
        "description": "Chart of accounts template for healthcare businesses.",
        "is_active": True,
    },
    {
        "code": "INFRASTRUCTURE",
        "name": "Infrastructure",
        "description": "Chart of accounts template for infrastructure businesses.",
        "is_active": True,
    },
    {
        "code": "HOLDING",
        "name": "Holding",
        "description": "Chart of accounts template for holding companies.",
        "is_active": True,
    },
]


async def seed_coa_industry_templates() -> None:
    async with AsyncSessionLocal() as session:
        stmt = insert(CoaIndustryTemplate).values(_INDUSTRY_TEMPLATES)
        stmt = stmt.on_conflict_do_nothing()
        await session.execute(stmt)
        await session.commit()


async def main() -> None:
    await seed_coa_industry_templates()
    print("CoA seed completed successfully")


if __name__ == "__main__":
    asyncio.run(main())
