from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.modules.coa.models import CoaLedgerAccount
from financeops.modules.coa.seeds.constants import SOFTWARE_SAAS_GROUPS
from financeops.modules.coa.seeds.software_saas_accounts import SOFTWARE_SAAS_LEDGER_ACCOUNTS
from financeops.modules.coa.seeds.utils import build_code


CATEGORY_METADATA: dict[str, dict[str, object]] = {
    "EQUITY_RESERVES": {"bs_pl_flag": "EQUITY", "asset_liability_class": None, "normal_balance": "CREDIT", "cash_flow_tag": "FINANCING", "cash_flow_method": "INDIRECT", "is_monetary": False},
    "LONG_TERM_BORROWINGS": {"bs_pl_flag": "LIABILITY", "asset_liability_class": "NON_CURRENT", "normal_balance": "CREDIT", "cash_flow_tag": "FINANCING", "cash_flow_method": "BOTH", "is_monetary": True},
    "SHORT_TERM_BORROWINGS": {"bs_pl_flag": "LIABILITY", "asset_liability_class": "CURRENT", "normal_balance": "CREDIT", "cash_flow_tag": "FINANCING", "cash_flow_method": "BOTH", "is_monetary": True},
    "TRADE_PAYABLES": {"bs_pl_flag": "LIABILITY", "asset_liability_class": "CURRENT", "normal_balance": "CREDIT", "cash_flow_tag": "OPERATING", "cash_flow_method": "BOTH", "is_monetary": True},
    "OTHER_CURRENT_LIABILITIES": {"bs_pl_flag": "LIABILITY", "asset_liability_class": "CURRENT", "normal_balance": "CREDIT", "cash_flow_tag": "OPERATING", "cash_flow_method": "BOTH", "is_monetary": True},
    "TANGIBLE_ASSETS": {"bs_pl_flag": "ASSET", "asset_liability_class": "NON_CURRENT", "normal_balance": "DEBIT", "cash_flow_tag": "INVESTING", "cash_flow_method": "BOTH", "is_monetary": False},
    "INTANGIBLE_ASSETS": {"bs_pl_flag": "ASSET", "asset_liability_class": "NON_CURRENT", "normal_balance": "DEBIT", "cash_flow_tag": "INVESTING", "cash_flow_method": "BOTH", "is_monetary": False},
    "CAPITAL_WIP": {"bs_pl_flag": "ASSET", "asset_liability_class": "NON_CURRENT", "normal_balance": "DEBIT", "cash_flow_tag": "INVESTING", "cash_flow_method": "BOTH", "is_monetary": False},
    "NON_CURRENT_INVESTMENTS": {"bs_pl_flag": "ASSET", "asset_liability_class": "NON_CURRENT", "normal_balance": "DEBIT", "cash_flow_tag": "INVESTING", "cash_flow_method": "BOTH", "is_monetary": True},
    "LONG_TERM_LOANS_ADVANCES": {"bs_pl_flag": "ASSET", "asset_liability_class": "NON_CURRENT", "normal_balance": "DEBIT", "cash_flow_tag": "OPERATING", "cash_flow_method": "BOTH", "is_monetary": True},
    "CURRENT_INVESTMENTS": {"bs_pl_flag": "ASSET", "asset_liability_class": "CURRENT", "normal_balance": "DEBIT", "cash_flow_tag": "INVESTING", "cash_flow_method": "BOTH", "is_monetary": True},
    "INVENTORIES": {"bs_pl_flag": "ASSET", "asset_liability_class": "CURRENT", "normal_balance": "DEBIT", "cash_flow_tag": "OPERATING", "cash_flow_method": "BOTH", "is_monetary": False},
    "TRADE_RECEIVABLES": {"bs_pl_flag": "ASSET", "asset_liability_class": "CURRENT", "normal_balance": "DEBIT", "cash_flow_tag": "OPERATING", "cash_flow_method": "BOTH", "is_monetary": True},
    "CASH_EQUIVALENTS": {"bs_pl_flag": "ASSET", "asset_liability_class": "CURRENT", "normal_balance": "DEBIT", "cash_flow_tag": "OPERATING", "cash_flow_method": "DIRECT", "is_monetary": True},
    "SHORT_TERM_LOANS_ADVANCES": {"bs_pl_flag": "ASSET", "asset_liability_class": "CURRENT", "normal_balance": "DEBIT", "cash_flow_tag": "OPERATING", "cash_flow_method": "BOTH", "is_monetary": True},
    "REVENUE": {"bs_pl_flag": "REVENUE", "asset_liability_class": None, "normal_balance": "CREDIT", "cash_flow_tag": "OPERATING", "cash_flow_method": "BOTH", "is_monetary": False},
    "OTHER_INCOME": {"bs_pl_flag": "REVENUE", "asset_liability_class": None, "normal_balance": "CREDIT", "cash_flow_tag": "OPERATING", "cash_flow_method": "BOTH", "is_monetary": False},
    "COGS": {"bs_pl_flag": "EXPENSE", "asset_liability_class": None, "normal_balance": "DEBIT", "cash_flow_tag": "OPERATING", "cash_flow_method": "BOTH", "is_monetary": False},
    "EMPLOYEE_BENEFITS": {"bs_pl_flag": "EXPENSE", "asset_liability_class": None, "normal_balance": "DEBIT", "cash_flow_tag": "OPERATING", "cash_flow_method": "INDIRECT", "is_monetary": False},
    "FINANCE_COSTS": {"bs_pl_flag": "EXPENSE", "asset_liability_class": None, "normal_balance": "DEBIT", "cash_flow_tag": "FINANCING", "cash_flow_method": "BOTH", "is_monetary": False},
    "DEPRECIATION_AMORTISATION": {"bs_pl_flag": "EXPENSE", "asset_liability_class": None, "normal_balance": "DEBIT", "cash_flow_tag": "EXCLUDED", "cash_flow_method": "INDIRECT", "is_monetary": False},
    "OTHER_EXPENSES": {"bs_pl_flag": "EXPENSE", "asset_liability_class": None, "normal_balance": "DEBIT", "cash_flow_tag": "OPERATING", "cash_flow_method": "BOTH", "is_monetary": False},
    "TAX": {"bs_pl_flag": "EXPENSE", "asset_liability_class": None, "normal_balance": "DEBIT", "cash_flow_tag": "OPERATING", "cash_flow_method": "INDIRECT", "is_monetary": False},
    "OCI": {"bs_pl_flag": "OCI", "asset_liability_class": None, "normal_balance": "CREDIT", "cash_flow_tag": "EXCLUDED", "cash_flow_method": "INDIRECT", "is_monetary": False},
}


def _is_contra_account(name: str) -> bool:
    lowered = name.lower()
    return "acc." in lowered or "allowance" in lowered


def _is_related_party(name: str) -> bool:
    lowered = name.lower()
    return "related" in lowered or "director" in lowered


def _is_tax_deductible(category: str, name: str) -> bool:
    if category == "TAX":
        return False
    lowered = name.lower()
    return "income tax" not in lowered and "mat / amt" not in lowered


async def seed_software_saas_ledger_accounts(
    session: AsyncSession,
    *,
    software_saas_template_id: str,
    subgroup_ids: dict[str, str],
) -> list[dict[str, str]]:
    category_group_code = {item["category"]: item["code"] for item in SOFTWARE_SAAS_GROUPS}
    generated_code_counts: defaultdict[str, int] = defaultdict(int)

    payload: list[dict[str, object]] = []
    for index, item in enumerate(SOFTWARE_SAAS_LEDGER_ACCOUNTS, start=1):
        category = item["category"]
        metadata = CATEGORY_METADATA[category]
        group_code = category_group_code[category]
        subgroup_code = f"{group_code}_DEFAULT"
        base_code = build_code("SAA", item["name"])
        generated_code_counts[base_code] += 1
        suffix = generated_code_counts[base_code]
        final_code = base_code if suffix == 1 else build_code("", f"{base_code}_{suffix}")
        payload.append(
            {
                "account_subgroup_id": subgroup_ids[subgroup_code],
                "industry_template_id": software_saas_template_id,
                "code": final_code,
                "name": item["name"],
                "description": f"SaaS template account - {category}",
                "normal_balance": metadata["normal_balance"],
                "cash_flow_tag": metadata["cash_flow_tag"],
                "cash_flow_method": metadata["cash_flow_method"],
                "bs_pl_flag": metadata["bs_pl_flag"],
                "asset_liability_class": metadata["asset_liability_class"],
                "is_monetary": bool(metadata["is_monetary"]),
                "is_related_party": _is_related_party(item["name"]),
                "is_tax_deductible": _is_tax_deductible(category, item["name"]),
                "is_control_account": _is_contra_account(item["name"]),
                "notes_reference": None,
                "is_active": True,
                "sort_order": index,
            }
        )

    stmt = insert(CoaLedgerAccount).values(payload)
    stmt = stmt.on_conflict_do_nothing()
    await session.execute(stmt)

    rows = (
        await session.execute(
            select(CoaLedgerAccount.id, CoaLedgerAccount.code, CoaLedgerAccount.name).where(
                CoaLedgerAccount.industry_template_id == software_saas_template_id
            )
        )
    ).all()
    by_name = {str(name): (str(identifier), str(code)) for identifier, code, name in rows}
    result: list[dict[str, str]] = []
    for item in SOFTWARE_SAAS_LEDGER_ACCOUNTS:
        identifier, account_code = by_name[item["name"]]
        result.append(
            {
                "id": identifier,
                "code": account_code,
                "name": item["name"],
                "category": item["category"],
            }
        )
    return result
