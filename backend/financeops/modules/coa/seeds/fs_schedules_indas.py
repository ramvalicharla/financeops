from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.modules.coa.models import CoaFsSchedule
from financeops.modules.coa.seeds.constants import INDAS_SCHEDULES


async def seed_indas_schedules(
    session: AsyncSession,
    *,
    classification_ids: dict[str, str],
) -> dict[str, str]:
    payload = []
    for schedule in INDAS_SCHEDULES:
        payload.append(
            {
                "fs_classification_id": classification_ids[schedule["classification_code"]],
                "gaap": schedule["gaap"],
                "code": schedule["code"],
                "name": schedule["name"],
                "schedule_number": schedule["schedule_number"],
                "sort_order": schedule["sort_order"],
                "is_active": True,
            }
        )
    stmt = insert(CoaFsSchedule).values(payload)
    stmt = stmt.on_conflict_do_nothing(constraint="uq_coa_fs_schedules_gaap_code")
    await session.execute(stmt)
    rows = (
        await session.execute(
            select(CoaFsSchedule.code, CoaFsSchedule.id).where(
                CoaFsSchedule.code.in_([item["code"] for item in INDAS_SCHEDULES])
            )
        )
    ).all()
    return {str(code): str(identifier) for code, identifier in rows}
