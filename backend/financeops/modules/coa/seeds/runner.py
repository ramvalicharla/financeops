from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from financeops.modules.coa.seeds.account_groups_software_saas import seed_software_saas_groups
from financeops.modules.coa.seeds.fs_classifications import seed_fs_classifications
from financeops.modules.coa.seeds.fs_line_items import seed_fs_line_items
from financeops.modules.coa.seeds.fs_schedules_ifrs import seed_ifrs_schedules
from financeops.modules.coa.seeds.fs_schedules_indas import seed_indas_schedules
from financeops.modules.coa.seeds.fs_sublines import seed_fs_sublines
from financeops.modules.coa.seeds.gaap_mappings_software_saas_indas import (
    seed_software_saas_indas_gaap_mappings,
)
from financeops.modules.coa.seeds.industry_templates import seed_industry_templates
from financeops.modules.coa.seeds.ledger_accounts_software_saas import (
    seed_software_saas_ledger_accounts,
)


async def run_coa_seeds(session: AsyncSession) -> None:
    template_ids = await seed_industry_templates(session)
    classification_ids = await seed_fs_classifications(session)
    indas_schedule_ids = await seed_indas_schedules(session, classification_ids=classification_ids)
    ifrs_schedule_ids = await seed_ifrs_schedules(session, classification_ids=classification_ids)

    schedule_ids = {**indas_schedule_ids, **ifrs_schedule_ids}
    line_item_ids = await seed_fs_line_items(session, schedule_ids=schedule_ids)
    subline_ids = await seed_fs_sublines(session, line_item_ids=line_item_ids)

    software_saas_template_id = template_ids["SOFTWARE_SAAS"]
    _, subgroup_ids = await seed_software_saas_groups(
        session,
        software_saas_template_id=software_saas_template_id,
        subline_ids=subline_ids,
    )
    ledger_accounts = await seed_software_saas_ledger_accounts(
        session,
        software_saas_template_id=software_saas_template_id,
        subgroup_ids=subgroup_ids,
    )
    await seed_software_saas_indas_gaap_mappings(
        session,
        ledger_accounts=ledger_accounts,
        schedule_ids=schedule_ids,
        line_item_ids=line_item_ids,
        subline_ids=subline_ids,
    )
