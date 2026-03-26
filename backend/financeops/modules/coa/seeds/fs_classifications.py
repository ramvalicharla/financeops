from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.modules.coa.models import CoaFsClassification
from financeops.modules.coa.seeds.constants import FS_CLASSIFICATIONS


async def seed_fs_classifications(session: AsyncSession) -> dict[str, str]:
    stmt = insert(CoaFsClassification).values(
        [
            {
                "code": code,
                "name": name,
                "sort_order": sort_order,
                "is_active": True,
            }
            for code, name, sort_order in FS_CLASSIFICATIONS
        ]
    )
    stmt = stmt.on_conflict_do_nothing(constraint="uq_coa_fs_classifications_code")
    await session.execute(stmt)
    rows = (
        await session.execute(
            select(CoaFsClassification.code, CoaFsClassification.id).where(
                CoaFsClassification.code.in_([code for code, _, _ in FS_CLASSIFICATIONS])
            )
        )
    ).all()
    return {str(code): str(identifier) for code, identifier in rows}
