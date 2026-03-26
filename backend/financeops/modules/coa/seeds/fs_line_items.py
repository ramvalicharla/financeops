from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.modules.coa.models import CoaFsLineItem
from financeops.modules.coa.seeds.constants import IFRS_LINE_ITEMS, INDAS_LINE_ITEMS


async def seed_fs_line_items(
    session: AsyncSession,
    *,
    schedule_ids: dict[str, str],
) -> dict[str, str]:
    all_line_items = [*INDAS_LINE_ITEMS, *IFRS_LINE_ITEMS]
    payload = [
        {
            "fs_schedule_id": schedule_ids[item["schedule_code"]],
            "code": item["code"],
            "name": item["name"],
            "bs_pl_flag": item["bs_pl_flag"],
            "asset_liability_class": item["asset_liability_class"],
            "sort_order": item["sort_order"],
            "is_active": True,
        }
        for item in all_line_items
    ]
    stmt = insert(CoaFsLineItem).values(payload)
    stmt = stmt.on_conflict_do_nothing(constraint="uq_coa_fs_line_items_schedule_code")
    await session.execute(stmt)
    rows = (
        await session.execute(
            select(CoaFsLineItem.code, CoaFsLineItem.id).where(
                CoaFsLineItem.code.in_([item["code"] for item in all_line_items])
            )
        )
    ).all()
    return {str(code): str(identifier) for code, identifier in rows}
