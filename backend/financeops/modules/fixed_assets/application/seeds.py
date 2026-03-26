from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.modules.coa.models import TenantCoaAccount
from financeops.modules.fixed_assets.models import FaAssetClass


STANDARD_INDIAN_ASSET_CLASSES: tuple[dict[str, object], ...] = (
    {
        "name": "Land - Freehold",
        "asset_type": "TANGIBLE",
        "default_method": "SLM",
        "default_useful_life_years": None,
        "it_act_block_number": None,
        "it_act_depreciation_rate": None,
    },
    {
        "name": "Land - Leasehold",
        "asset_type": "TANGIBLE",
        "default_method": "SLM",
        "default_useful_life_years": 30,
        "it_act_block_number": None,
        "it_act_depreciation_rate": None,
    },
    {
        "name": "Buildings - Factory",
        "asset_type": "TANGIBLE",
        "default_method": "SLM",
        "default_useful_life_years": 30,
        "it_act_block_number": 1,
        "it_act_depreciation_rate": Decimal("0.1000"),
    },
    {
        "name": "Buildings - Office",
        "asset_type": "TANGIBLE",
        "default_method": "SLM",
        "default_useful_life_years": 30,
        "it_act_block_number": 1,
        "it_act_depreciation_rate": Decimal("0.1000"),
    },
    {
        "name": "Plant & Machinery - General",
        "asset_type": "TANGIBLE",
        "default_method": "SLM",
        "default_useful_life_years": 15,
        "it_act_block_number": 2,
        "it_act_depreciation_rate": Decimal("0.1500"),
    },
    {
        "name": "Plant & Machinery - Computers & Software",
        "asset_type": "TANGIBLE",
        "default_method": "SLM",
        "default_useful_life_years": 3,
        "it_act_block_number": 3,
        "it_act_depreciation_rate": Decimal("0.4000"),
    },
    {
        "name": "Furniture & Fixtures",
        "asset_type": "TANGIBLE",
        "default_method": "SLM",
        "default_useful_life_years": 10,
        "it_act_block_number": 4,
        "it_act_depreciation_rate": Decimal("0.1000"),
    },
    {
        "name": "Vehicles - Motor Car",
        "asset_type": "TANGIBLE",
        "default_method": "SLM",
        "default_useful_life_years": 8,
        "it_act_block_number": 5,
        "it_act_depreciation_rate": Decimal("0.1500"),
    },
    {
        "name": "Vehicles - Commercial",
        "asset_type": "TANGIBLE",
        "default_method": "SLM",
        "default_useful_life_years": 8,
        "it_act_block_number": 6,
        "it_act_depreciation_rate": Decimal("0.3000"),
    },
    {
        "name": "Office Equipment",
        "asset_type": "TANGIBLE",
        "default_method": "SLM",
        "default_useful_life_years": 5,
        "it_act_block_number": 7,
        "it_act_depreciation_rate": Decimal("0.1500"),
    },
    {
        "name": "Air Conditioning",
        "asset_type": "TANGIBLE",
        "default_method": "SLM",
        "default_useful_life_years": 5,
        "it_act_block_number": 8,
        "it_act_depreciation_rate": Decimal("0.1500"),
    },
    {
        "name": "Goodwill",
        "asset_type": "INTANGIBLE",
        "default_method": "SLM",
        "default_useful_life_years": 10,
        "it_act_block_number": None,
        "it_act_depreciation_rate": None,
    },
    {
        "name": "Software - Purchased",
        "asset_type": "INTANGIBLE",
        "default_method": "SLM",
        "default_useful_life_years": 3,
        "it_act_block_number": 9,
        "it_act_depreciation_rate": Decimal("0.2500"),
    },
    {
        "name": "Software - Internally Developed",
        "asset_type": "INTANGIBLE",
        "default_method": "SLM",
        "default_useful_life_years": 3,
        "it_act_block_number": 9,
        "it_act_depreciation_rate": Decimal("0.2500"),
    },
    {
        "name": "Customer Relationships",
        "asset_type": "INTANGIBLE",
        "default_method": "SLM",
        "default_useful_life_years": 5,
        "it_act_block_number": None,
        "it_act_depreciation_rate": None,
    },
    {
        "name": "Non-Compete Agreements",
        "asset_type": "INTANGIBLE",
        "default_method": "SLM",
        "default_useful_life_years": 5,
        "it_act_block_number": None,
        "it_act_depreciation_rate": None,
    },
    {
        "name": "Trademarks & Patents",
        "asset_type": "INTANGIBLE",
        "default_method": "SLM",
        "default_useful_life_years": 10,
        "it_act_block_number": None,
        "it_act_depreciation_rate": None,
    },
    {
        "name": "Right-of-Use - Buildings",
        "asset_type": "ROU",
        "default_method": "SLM",
        "default_useful_life_years": 10,
        "it_act_block_number": None,
        "it_act_depreciation_rate": None,
    },
    {
        "name": "Right-of-Use - Equipment",
        "asset_type": "ROU",
        "default_method": "SLM",
        "default_useful_life_years": 5,
        "it_act_block_number": None,
        "it_act_depreciation_rate": None,
    },
)


def _match_account_ids(accounts: list[TenantCoaAccount], name: str) -> tuple[uuid.UUID | None, uuid.UUID | None, uuid.UUID | None]:
    lowered = name.lower()

    def _pick(predicate: str) -> uuid.UUID | None:
        for account in accounts:
            dn = account.display_name.lower()
            if predicate in dn:
                return account.id
        return None

    asset_id = None
    accum_dep_id = None
    dep_expense_id = None

    if "building" in lowered or "land" in lowered:
        asset_id = _pick("buildings") or _pick("land")
    elif "software" in lowered or "intangible" in lowered or "goodwill" in lowered:
        asset_id = _pick("software") or _pick("intangible") or _pick("goodwill")
    elif "right-of-use" in lowered:
        asset_id = _pick("right-of-use") or _pick("rou")
    else:
        asset_id = _pick("plant") or _pick("equipment") or _pick("furniture")

    accum_dep_id = _pick("acc. depreciation") or _pick("acc. amortisation")
    dep_expense_id = _pick("depreciation") or _pick("amortisation")
    return asset_id, accum_dep_id, dep_expense_id


async def seed_standard_indian_asset_classes(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
) -> int:
    existing = (
        await session.execute(
            select(FaAssetClass.name).where(
                FaAssetClass.tenant_id == tenant_id,
                FaAssetClass.entity_id == entity_id,
            )
        )
    ).scalars().all()
    existing_names = set(existing)

    tenant_accounts = (
        await session.execute(
            select(TenantCoaAccount).where(TenantCoaAccount.tenant_id == tenant_id)
        )
    ).scalars().all()

    created_count = 0
    for row in STANDARD_INDIAN_ASSET_CLASSES:
        name = str(row["name"])
        if name in existing_names:
            continue
        asset_id, accum_dep_id, dep_expense_id = _match_account_ids(list(tenant_accounts), name)
        session.add(
            FaAssetClass(
                tenant_id=tenant_id,
                entity_id=entity_id,
                name=name,
                asset_type=str(row["asset_type"]),
                default_method=str(row["default_method"]),
                default_useful_life_years=row.get("default_useful_life_years"),
                default_residual_pct=Decimal("0.0500"),
                it_act_block_number=row.get("it_act_block_number"),
                it_act_depreciation_rate=row.get("it_act_depreciation_rate"),
                coa_asset_account_id=asset_id,
                coa_accum_dep_account_id=accum_dep_id,
                coa_dep_expense_account_id=dep_expense_id,
                is_active=True,
            )
        )
        created_count += 1

    await session.flush()
    return created_count


__all__ = ["seed_standard_indian_asset_classes", "STANDARD_INDIAN_ASSET_CLASSES"]
