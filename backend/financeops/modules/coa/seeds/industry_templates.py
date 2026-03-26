from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.modules.coa.models import CoaIndustryTemplate
from financeops.modules.coa.seeds.constants import INDUSTRY_TEMPLATES


async def seed_industry_templates(session: AsyncSession) -> dict[str, str]:
    stmt = insert(CoaIndustryTemplate).values(
        [
            {
                "code": item["code"],
                "name": item["name"],
                "description": item["description"],
                "is_active": True,
            }
            for item in INDUSTRY_TEMPLATES
        ]
    )
    stmt = stmt.on_conflict_do_nothing(constraint="uq_coa_industry_templates_code")
    await session.execute(stmt)
    rows = (
        await session.execute(
            select(CoaIndustryTemplate.code, CoaIndustryTemplate.id).where(
                CoaIndustryTemplate.code.in_([item["code"] for item in INDUSTRY_TEMPLATES])
            )
        )
    ).all()
    return {str(code): str(identifier) for code, identifier in rows}
