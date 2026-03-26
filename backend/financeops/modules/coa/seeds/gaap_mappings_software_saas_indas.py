from __future__ import annotations

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.modules.coa.models import CoaGaapMapping
from financeops.modules.coa.seeds.constants import INDAS_LINE_ITEMS, INDAS_SUBLINES


DEFAULT_SUBLINE_BY_CATEGORY: dict[str, str] = {
    "EQUITY_RESERVES": "RESERVES_SURPLUS",
    "LONG_TERM_BORROWINGS": "LONG_TERM_BORROWINGS",
    "SHORT_TERM_BORROWINGS": "SHORT_TERM_BORROWINGS",
    "TRADE_PAYABLES": "TRADE_PAYABLES_OTHERS",
    "OTHER_CURRENT_LIABILITIES": "OTHER_CURRENT_LIAB",
    "TANGIBLE_ASSETS": "FIXED_ASSETS_TANGIBLE",
    "INTANGIBLE_ASSETS": "FIXED_ASSETS_INTANGIBLE",
    "CAPITAL_WIP": "CAPITAL_WIP",
    "NON_CURRENT_INVESTMENTS": "NON_CURRENT_INVESTMENTS",
    "LONG_TERM_LOANS_ADVANCES": "LONG_TERM_LOANS_ADVANCES",
    "CURRENT_INVESTMENTS": "CURRENT_INVESTMENTS",
    "INVENTORIES": "INVENTORIES",
    "TRADE_RECEIVABLES": "TRADE_RECEIVABLES",
    "CASH_EQUIVALENTS": "CASH_EQUIVALENTS",
    "SHORT_TERM_LOANS_ADVANCES": "SHORT_TERM_LOANS_ADVANCES",
    "REVENUE": "OPERATING_REVENUE",
    "OTHER_INCOME": "OTHER_INCOME_SUBLINE",
    "COGS": "COGS_SUBLINE",
    "EMPLOYEE_BENEFITS": "EMPLOYEE_BENEFITS",
    "FINANCE_COSTS": "FINANCE_COSTS",
    "DEPRECIATION_AMORTISATION": "DEPR_AMORT",
    "OTHER_EXPENSES": "OTHER_EXPENSES",
    "TAX": "CURRENT_TAX",
    "OCI": "OCI_ITEMS",
}


def _resolve_subline_code(category: str, name: str) -> str:
    lowered = name.lower()
    if category == "EQUITY_RESERVES" and "share capital" in lowered:
        return "SHARE_CAPITAL"
    if category == "TRADE_PAYABLES" and "msme" in lowered:
        return "TRADE_PAYABLES_MSME"
    if category == "OTHER_CURRENT_LIABILITIES" and ("provision" in lowered or "tax" in lowered):
        return "SHORT_TERM_PROVISIONS"
    if category == "LONG_TERM_LOANS_ADVANCES" and "deferred tax" in lowered:
        return "DTA_NET"
    if category == "SHORT_TERM_LOANS_ADVANCES" and ("gst input credit" in lowered or "tds receivable" in lowered):
        return "OTHER_CURRENT_ASSETS"
    if category == "TAX" and "deferred" in lowered:
        return "DEFERRED_TAX"
    return DEFAULT_SUBLINE_BY_CATEGORY[category]


async def seed_software_saas_indas_gaap_mappings(
    session: AsyncSession,
    *,
    ledger_accounts: list[dict[str, str]],
    schedule_ids: dict[str, str],
    line_item_ids: dict[str, str],
    subline_ids: dict[str, str],
) -> int:
    line_by_subline = {item["code"]: item["line_item_code"] for item in INDAS_SUBLINES}
    schedule_by_line = {item["code"]: item["schedule_code"] for item in INDAS_LINE_ITEMS}

    payload: list[dict[str, object]] = []
    for index, account in enumerate(ledger_accounts, start=1):
        subline_code = _resolve_subline_code(account["category"], account["name"])
        line_item_code = line_by_subline[subline_code]
        schedule_code = schedule_by_line[line_item_code]
        payload.append(
            {
                "ledger_account_id": account["id"],
                "gaap": "INDAS",
                "fs_schedule_id": schedule_ids[schedule_code],
                "fs_line_item_id": line_item_ids[line_item_code],
                "fs_subline_id": subline_ids.get(subline_code),
                "presentation_label": account["name"],
                "sort_order": index,
                "is_active": True,
            }
        )
    stmt = insert(CoaGaapMapping).values(payload)
    stmt = stmt.on_conflict_do_nothing(constraint="uq_coa_gaap_mappings_ledger_gaap")
    await session.execute(stmt)
    return len(payload)
