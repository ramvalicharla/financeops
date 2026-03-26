from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.modules.coa.models import CoaFsSubline
from financeops.modules.coa.seeds.constants import INDAS_SUBLINES


async def seed_fs_sublines(
    session: AsyncSession,
    *,
    line_item_ids: dict[str, str],
) -> dict[str, str]:
    payload = [
        {
            "fs_line_item_id": line_item_ids[item["line_item_code"]],
            "code": item["code"],
            "name": item["name"],
            "sort_order": item["sort_order"],
            "is_active": True,
        }
        for item in INDAS_SUBLINES
    ]
    stmt = insert(CoaFsSubline).values(payload)
    stmt = stmt.on_conflict_do_nothing(constraint="uq_coa_fs_sublines_line_code")
    await session.execute(stmt)
    rows = (
        await session.execute(
            select(CoaFsSubline.code, CoaFsSubline.id).where(
                CoaFsSubline.code.in_([item["code"] for item in INDAS_SUBLINES])
            )
        )
    ).all()
    return {str(code): str(identifier) for code, identifier in rows}
