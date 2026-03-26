from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.modules.coa.models import CoaAccountGroup, CoaAccountSubgroup
from financeops.modules.coa.seeds.constants import SOFTWARE_SAAS_GROUPS


async def seed_software_saas_groups(
    session: AsyncSession,
    *,
    software_saas_template_id: str,
    subline_ids: dict[str, str],
) -> tuple[dict[str, str], dict[str, str]]:
    group_payload = [
        {
            "industry_template_id": software_saas_template_id,
            "fs_subline_id": subline_ids[item["subline_code"]],
            "code": item["code"],
            "name": item["name"],
            "sort_order": item["sort_order"],
            "is_active": True,
        }
        for item in SOFTWARE_SAAS_GROUPS
    ]
    group_stmt = insert(CoaAccountGroup).values(group_payload)
    group_stmt = group_stmt.on_conflict_do_nothing(constraint="uq_coa_account_groups_template_code")
    await session.execute(group_stmt)

    groups = (
        await session.execute(
            select(CoaAccountGroup.code, CoaAccountGroup.id).where(
                CoaAccountGroup.industry_template_id == software_saas_template_id
            )
        )
    ).all()
    group_ids = {str(code): str(identifier) for code, identifier in groups}

    subgroup_payload = [
        {
            "account_group_id": group_ids[item["code"]],
            "code": f"{item['code']}_DEFAULT",
            "name": f"{item['name']} - Default",
            "sort_order": 1,
            "is_active": True,
        }
        for item in SOFTWARE_SAAS_GROUPS
    ]
    subgroup_stmt = insert(CoaAccountSubgroup).values(subgroup_payload)
    subgroup_stmt = subgroup_stmt.on_conflict_do_nothing(constraint="uq_coa_account_subgroups_group_code")
    await session.execute(subgroup_stmt)

    subgroups = (
        await session.execute(
            select(CoaAccountSubgroup.code, CoaAccountSubgroup.id).where(
                CoaAccountSubgroup.account_group_id.in_(list(group_ids.values()))
            )
        )
    ).all()
    subgroup_ids = {str(code): str(identifier) for code, identifier in subgroups}
    return group_ids, subgroup_ids
